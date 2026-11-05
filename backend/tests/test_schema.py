from sqlalchemy import text

from app.db_models import EMBEDDING_DIM


def test_chunk_tsv_is_generated_and_vector_search_works(session_factory):
    with session_factory() as session:
        session.execute(
            text(
                "INSERT INTO meetings (id, title, source_name, source_type, content_hash) "
                "VALUES ('m1', 'Planning', 'planning.txt', 'txt', 'h1')"
            )
        )
        session.execute(
            text(
                "INSERT INTO chunks (meeting_id, first_turn_idx, last_turn_idx, speakers, text, start_ts, embedding) "
                "VALUES ('m1', 0, 1, ARRAY['Alice'], 'We decided to postpone the launch', 0, :emb)"
            ),
            {"emb": str([1.0] + [0.0] * (EMBEDDING_DIM - 1))},
        )
        session.commit()

        fts_hit = session.execute(
            text("SELECT count(*) FROM chunks WHERE tsv @@ plainto_tsquery('english', 'launches postponed')")
        ).scalar()
        nearest = session.execute(
            text("SELECT meeting_id FROM chunks ORDER BY embedding <=> :q LIMIT 1"),
            {"q": str([0.9] + [0.1] * (EMBEDDING_DIM - 1))},
        ).scalar()

    assert fts_hit == 1  # stemming: "launches postponed" matches "postpone the launch"
    assert nearest == "m1"
