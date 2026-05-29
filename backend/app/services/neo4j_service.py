"""
Neo4j Service - Knowledge graph storage and querying
Responsible for triple storage, subgraph retrieval, and statistics
"""

from typing import Optional
from datetime import datetime

from app.core.config import get_settings
from app.core.logger import logger
from app.models.database import neo4j_conn


class Neo4jService:
    """Neo4j knowledge graph service"""

    async def store_triples(
        self,
        triples: list[dict],
        chunk_id: str,
        file_id: str,
        filename: str = "",
        upload_time: str = "",
    ) -> tuple[int, int]:
        """
        Store triples into Neo4j and establish Chunk-to-Entity associations

        Nodes and relationships created:
        - (chunk:Chunk {chunk_id, file_id, filename, upload_time})
        - (entity:Entity {name})
        - (chunk)-[:CONTAINS]->(entity)
        - (head:Entity)-[relation]->(tail:Entity)

        Args:
            triples: List of triples
            chunk_id: Source text block ID
            file_id: Source file ID
            filename: File name
            upload_time: Upload timestamp string

        Returns:
            (entity count, relation count)
        """
        if not triples:
            return 0, 0

        entity_count = 0
        relation_count = 0

        async with neo4j_conn.get_session() as session:
            # 1. Create Chunk node
            await session.run(
                """
                MERGE (c:Chunk {chunk_id: $chunk_id})
                SET c.file_id = $file_id,
                    c.filename = $filename,
                    c.upload_time = $upload_time
                """,
                chunk_id=chunk_id,
                file_id=file_id,
                filename=filename,
                upload_time=upload_time,
            )

            # 2. Process each triple
            for triple in triples:
                head = triple["head"]
                relation = triple["relation"]
                tail = triple["tail"]

                if not head or not relation or not tail:
                    continue

                try:
                    # Create entity nodes and relationships, and establish Chunk -> Entity association
                    await session.run(
                        """
                        // Create or merge head entity and tail entity
                        MERGE (h:Entity {name: $head})
                        MERGE (t:Entity {name: $tail})

                        // Create relationship between entities (using dynamic relationship type)
                        MERGE (h)-[r:RELATES_TO {type: $relation}]->(t)

                        // Use WITH to separate update clauses from subsequent queries, avoiding syntax errors
                        WITH h, t

                        // Establish Chunk-to-Entity CONTAINS association
                        MERGE (c:Chunk {chunk_id: $chunk_id})
                        MERGE (c)-[:CONTAINS]->(h)
                        MERGE (c)-[:CONTAINS]->(t)
                        """,
                        head=head,
                        tail=tail,
                        relation=relation,
                        chunk_id=chunk_id,
                    )
                    entity_count += 2
                    relation_count += 1

                except Exception as e:
                    logger.warning(
                        "Failed to store triple [%s -[%s]-> %s]: %s",
                        head, relation, tail, str(e),
                    )
                    continue

        logger.info(
            "Chunk %s: stored %d entities, %d relations",
            chunk_id, entity_count, relation_count,
        )
        return entity_count, relation_count

    async def get_subgraph_by_chunk_ids(
        self,
        chunk_ids: list[str],
        max_depth: int = 2,
    ) -> dict:
        """
        Query the subgraph associated with given text block IDs

        Retrieval logic:
        1. Find all Entities associated with Chunks (first order)
        2. Expand to neighbors of these Entities (second order)
        3. Collect all relationships

        Args:
            chunk_ids: List of text block IDs
            max_depth: Maximum expansion depth (1 or 2)

        Returns:
            {"entities": [...], "relations": [...]}
        """
        if not chunk_ids:
            return {"entities": [], "relations": []}

        async with neo4j_conn.get_session() as session:
            # Query first and second order subgraph
            if max_depth >= 2:
                query = """
                // Find entities associated with the specified chunks
                MATCH (c:Chunk)-[:CONTAINS]->(e:Entity)
                WHERE c.chunk_id IN $chunk_ids

                // Expand to direct relationships of these entities
                OPTIONAL MATCH (e)-[r1:RELATES_TO]-(neighbor:Entity)

                // Collect all involved entities and relationships
                WITH collect(DISTINCT e) + collect(DISTINCT neighbor) AS all_entities,
                     collect(DISTINCT r1) AS all_rels

                UNWIND all_entities AS ent
                UNWIND all_rels AS rel

                RETURN collect(DISTINCT {name: ent.name}) AS entities,
                       collect(DISTINCT {
                           head: startNode(rel).name,
                           relation: rel.type,
                           tail: endNode(rel).name
                       }) AS relations
                """
            else:
                query = """
                MATCH (c:Chunk)-[:CONTAINS]->(e:Entity)
                WHERE c.chunk_id IN $chunk_ids
                OPTIONAL MATCH (e)-[r1:RELATES_TO]-(neighbor:Entity)

                WITH collect(DISTINCT e) + collect(DISTINCT neighbor) AS all_entities,
                     collect(DISTINCT r1) AS all_rels

                UNWIND all_entities AS ent
                UNWIND all_rels AS rel

                RETURN collect(DISTINCT {name: ent.name}) AS entities,
                       collect(DISTINCT {
                           head: startNode(rel).name,
                           relation: rel.type,
                           tail: endNode(rel).name
                       }) AS relations
                """

            result = await session.run(query, chunk_ids=chunk_ids)
            records = await result.data()

            if records and records[0]:
                entities = records[0].get("entities", [])
                relations = records[0].get("relations", [])

                # Filter out None values
                entities = [e for e in entities if e and e.get("name")]
                relations = [r for r in relations if r and r.get("head") and r.get("tail")]

                logger.info(
                    "Subgraph query complete: %d entities, %d relations",
                    len(entities), len(relations),
                )
                return {"entities": entities, "relations": relations}

            return {"entities": [], "relations": []}

    async def get_total_nodes(self) -> int:
        """Get total node count in the graph"""
        try:
            async with neo4j_conn.get_session() as session:
                result = await session.run(
                    "MATCH (n) RETURN count(n) AS count"
                )
                records = await result.data()
                return records[0]["count"] if records else 0
        except Exception as e:
            logger.error("Failed to get Neo4j node count: %s", str(e))
            return 0

    async def get_total_edges(self) -> int:
        """Get total relationship count in the graph"""
        try:
            async with neo4j_conn.get_session() as session:
                result = await session.run(
                    "MATCH ()-[r]->() RETURN count(r) AS count"
                )
                records = await result.data()
                return records[0]["count"] if records else 0
        except Exception as e:
            logger.error("Failed to get Neo4j edge count: %s", str(e))
            return 0

    async def get_total_pdfs(self) -> int:
        """Get total count of processed PDF files (based on distinct file_id of Chunk nodes)"""
        try:
            async with neo4j_conn.get_session() as session:
                result = await session.run(
                    "MATCH (c:Chunk) RETURN count(DISTINCT c.file_id) AS count"
                )
                records = await result.data()
                return records[0]["count"] if records else 0
        except Exception as e:
            logger.error("Failed to get PDF count: %s", str(e))
            return 0

    async def list_pdfs(self) -> list[dict]:
        """
        Get file info of all uploaded PDFs

        Returns:
            [{"file_id": "...", "filename": "...", "upload_time": "...", "total_chunks": N}, ...]
        """
        try:
            async with neo4j_conn.get_session() as session:
                result = await session.run(
                    """
                    MATCH (c:Chunk)
                    WITH c.file_id AS file_id,
                         c.filename AS filename,
                         c.upload_time AS upload_time
                    RETURN file_id, filename, upload_time, count(*) AS total_chunks
                    ORDER BY upload_time DESC
                    """
                )
                records = await result.data()
                # Deduplicate: since the same file_id may have multiple chunks, retain the first record's info
                seen = {}
                for r in records:
                    fid = r.get("file_id")
                    if fid and fid not in seen:
                        seen[fid] = {
                            "file_id": fid,
                            "filename": r.get("filename") or "",
                            "upload_time": r.get("upload_time") or "",
                            "total_chunks": r.get("total_chunks", 0),
                        }
                logger.info("PDF list retrieved successfully: %d files", len(seen))
                return list(seen.values())
        except Exception as e:
            logger.error("Failed to get PDF list: %s", str(e))
            return []

    async def clear_all(self) -> None:
        """Clear all nodes and relationships in the Neo4j database"""
        try:
            async with neo4j_conn.get_session() as session:
                await session.run("MATCH (n) DETACH DELETE n")
                logger.info("Neo4j database has been cleared")
        except Exception as e:
            logger.error("Failed to clear Neo4j database: %s", str(e))
            raise RuntimeError(f"Failed to clear Neo4j database: {str(e)}")


# Global singleton
_neo4j_service: Optional[Neo4jService] = None


def get_neo4j_service() -> Neo4jService:
    """Get Neo4j service singleton"""
    global _neo4j_service
    if _neo4j_service is None:
        _neo4j_service = Neo4jService()
    return _neo4j_service