--
-- PostgreSQL database dump
--

\restrict Uxr0gMXIoGjXsdaFWARONqyAiYDeC6d96MUkEPr9k5UXi7dRMVJbCkB5nUgI0g9

-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

DROP INDEX IF EXISTS public.ix_runs_created_at;
DROP INDEX IF EXISTS public.ix_runs_artefacts;
DROP INDEX IF EXISTS public.ix_paper_scores_run_id;
DROP INDEX IF EXISTS public.ix_paper_scores_doi;
DROP INDEX IF EXISTS public.ix_artefact_scores_run_id;
ALTER TABLE IF EXISTS ONLY public.paper_scores DROP CONSTRAINT IF EXISTS uq_paper_scores_run_paper_reviewer;
ALTER TABLE IF EXISTS ONLY public.artefact_scores DROP CONSTRAINT IF EXISTS uq_artefact_scores_run_artefact_reviewer;
ALTER TABLE IF EXISTS ONLY public.runs DROP CONSTRAINT IF EXISTS runs_run_id_key;
ALTER TABLE IF EXISTS ONLY public.runs DROP CONSTRAINT IF EXISTS runs_pkey;
ALTER TABLE IF EXISTS ONLY public.paper_scores DROP CONSTRAINT IF EXISTS paper_scores_pkey;
ALTER TABLE IF EXISTS ONLY public.artefact_scores DROP CONSTRAINT IF EXISTS artefact_scores_pkey;
DROP TABLE IF EXISTS public.runs;
DROP TABLE IF EXISTS public.paper_scores;
DROP TABLE IF EXISTS public.artefact_scores;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: artefact_scores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.artefact_scores (
    id uuid NOT NULL,
    run_id character varying(64) NOT NULL,
    artefact character varying(64) NOT NULL,
    score smallint NOT NULL,
    note text,
    reviewer character varying(64) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_artefact_scores_range CHECK (((score >= 1) AND (score <= 5)))
);


--
-- Name: paper_scores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.paper_scores (
    id uuid NOT NULL,
    run_id character varying(64) NOT NULL,
    paper_id character varying(64) NOT NULL,
    doi text,
    title text NOT NULL,
    score smallint NOT NULL,
    note text,
    reviewer character varying(64) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_paper_scores_range CHECK (((score >= 1) AND (score <= 5)))
);


--
-- Name: runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.runs (
    id uuid NOT NULL,
    run_id character varying(64) NOT NULL,
    research_question text NOT NULL,
    config jsonb NOT NULL,
    status character varying(16) NOT NULL,
    artefacts jsonb NOT NULL,
    metrics jsonb NOT NULL,
    error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    CONSTRAINT ck_runs_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'running'::character varying, 'completed'::character varying, 'failed'::character varying])::text[])))
);


--
-- Data for Name: artefact_scores; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.artefact_scores (id, run_id, artefact, score, note, reviewer, created_at) FROM stdin;
\.


--
-- Data for Name: paper_scores; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.paper_scores (id, run_id, paper_id, doi, title, score, note, reviewer, created_at) FROM stdin;
\.


--
-- Data for Name: runs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.runs (id, run_id, research_question, config, status, artefacts, metrics, error, created_at, completed_at) FROM stdin;
7ae9ad65-7798-4543-8ca7-1923096640bd	fixture	How do multi-agent RAG systems reduce hallucination?	{}	completed	[{"name": "claims.json", "path": "outputs\\\\runs\\\\fixture\\\\claims.json", "bytes": 26693, "sha256": null}, {"name": "config.json", "path": "outputs\\\\runs\\\\fixture\\\\config.json", "bytes": 1287, "sha256": null}, {"name": "corpus.json", "path": "outputs\\\\runs\\\\fixture\\\\corpus.json", "bytes": 1550084, "sha256": null}, {"name": "insights.csv", "path": "outputs\\\\runs\\\\fixture\\\\insights.csv", "bytes": 10700, "sha256": null}, {"name": "refs.bib", "path": "outputs\\\\runs\\\\fixture\\\\refs.bib", "bytes": 3109, "sha256": null}, {"name": "review.md", "path": "outputs\\\\runs\\\\fixture\\\\review.md", "bytes": 11558, "sha256": null}, {"name": "trace.jsonl", "path": "outputs\\\\runs\\\\fixture\\\\trace.jsonl", "bytes": 46884, "sha256": null}]	{"papers": 551, "dropped_claims": 3, "grounding_score": 0.8636, "verified_claims": 19}	\N	2026-08-28 19:47:22.579218+05:30	2026-08-28 19:47:22.609393+05:30
fd238650-7f18-4371-8bca-bccd95d2aa9b	dead	q	{"llm": {"model": "openai/gpt-oss-120b", "provider": "baseten", "cache_dir": "data/llm_cache", "max_tokens": 2048, "max_retries": 5, "temperature": 0.1, "planner_model": "openai/gpt-oss-120b", "reasoning_effort": "low", "tokens_per_minute": 0, "requests_per_minute": 60}, "output": {"formats": ["markdown", "csv", "bibtex"], "runs_dir": "outputs/runs", "citation_style": "ieee"}, "review": {"year_min": 2019, "max_papers": 10, "min_papers": 20, "max_iterations": 3, "coverage_threshold": 0.8, "grounding_threshold": 0.7}, "sources": {"enabled": ["openalex", "arxiv"], "max_per_source": 25}, "verifier": {"onnx_path": "data/models/verifier-onnx", "tokenizer": "microsoft/deberta-v3-small", "support_threshold": 0.7}, "retrieval": {"rrf_k": 60, "fusion": "rrf", "rerank": true, "dense_k": 30, "final_k": 12, "reranker": "data/models/reranker-mixed-onnx", "sparse_k": 30, "chunk_size": 1200, "chunk_overlap": 200}, "embeddings": {"model": "BAAI/bge-small-en-v1.5", "device": "cpu", "batch_size": 32}}	failed	[]	{}	no review produced; every section was rejected or failed	2026-08-28 19:57:59.802612+05:30	2026-08-30 22:47:50.889236+05:30
30f780c7-42f6-496e-a382-d715ac8b7b66	pytest-registry-roundtrip	does it round-trip?	{"a": 1}	completed	[{"name": "review.md", "path": "/tmp/review.md", "bytes": 99, "sha256": "cafe"}]	{"papers": 3}	\N	2026-08-30 22:48:01.200324+05:30	2026-08-30 22:48:01.208618+05:30
8519b056-43c3-4320-8a1b-cd26dcd96094	t410_cap25	How do multi-agent retrieval-augmented systems reduce hallucination in automated literature review?	{"llm": {"model": "openai/gpt-oss-20b", "provider": null, "cache_dir": "data/llm_cache", "max_tokens": 2048, "max_retries": 5, "temperature": 0.1, "planner_model": "openai/gpt-oss-20b", "reasoning_effort": "low", "tokens_per_minute": 8000, "requests_per_minute": 30}, "output": {"formats": ["markdown", "csv", "bibtex"], "runs_dir": "outputs/runs", "citation_style": "ieee"}, "review": {"year_min": 2019, "max_papers": 10, "min_papers": 20, "max_iterations": 3, "coverage_threshold": 0.8, "grounding_threshold": 0.7}, "sources": {"enabled": ["openalex", "arxiv"], "max_per_source": 25}, "verifier": {"onnx_path": "data/models/verifier-onnx", "tokenizer": "microsoft/deberta-v3-small", "support_threshold": 0.7}, "retrieval": {"rrf_k": 60, "fusion": "rrf", "rerank": true, "dense_k": 30, "final_k": 12, "reranker": "data/models/reranker-mixed-onnx", "sparse_k": 30, "chunk_size": 1200, "chunk_overlap": 200}, "embeddings": {"model": "BAAI/bge-small-en-v1.5", "device": "cpu", "batch_size": 32}}	completed	[{"name": "review.md", "path": "outputs\\\\runs\\\\t410_cap25\\\\review.md", "bytes": 13545, "sha256": "39367e756cb4c7668ad3d9402130cfe652f1441a9370c7c4602606055131eb44"}, {"name": "refs.bib", "path": "outputs\\\\runs\\\\t410_cap25\\\\refs.bib", "bytes": 3803, "sha256": "7182f6a8ba0b1bdad2388f9c8843c747be579dbbb87e7f39b72ad605433d7b04"}, {"name": "insights.csv", "path": "outputs\\\\runs\\\\t410_cap25\\\\insights.csv", "bytes": 11884, "sha256": "f0b359455b581e67af2109e2cbc0d7408f9181f61b3c07970a7fe510442f466f"}, {"name": "corpus.json", "path": "outputs\\\\runs\\\\t410_cap25\\\\corpus.json", "bytes": 4516033, "sha256": "c4f29c07b5f93580f5ed2acbf8f5ed4e6f28782b8fe31a19cba463f02018dc14"}, {"name": "claims.json", "path": "outputs\\\\runs\\\\t410_cap25\\\\claims.json", "bytes": 23763, "sha256": "7a7b4cfe054863d84b021a73ab4d57c23ab842d602c13553c336a5afb08a3c62"}, {"name": "config.json", "path": "outputs\\\\runs\\\\t410_cap25\\\\config.json", "bytes": 1281, "sha256": "4b48a47763c8815d6b68463bb030e0144dcd887ea828b839ccccf7f5d4f7689d"}]	{"papers": 2217, "insights": 10, "decisions": ["WRITE", "WRITE"], "iterations": 0, "dropped_claims": 5, "grounding_score": 0.7619047619047619, "verified_claims": 16}	\N	2026-08-29 15:26:09.527794+05:30	2026-08-29 16:07:32.875914+05:30
c6aa8674-6f09-41e1-b813-0423ca942d3e	t410_cap100	How do multi-agent retrieval-augmented systems reduce hallucination in automated literature review?	{"llm": {"model": "openai/gpt-oss-20b", "provider": null, "cache_dir": "data/llm_cache", "max_tokens": 2048, "max_retries": 5, "temperature": 0.1, "planner_model": "openai/gpt-oss-20b", "reasoning_effort": "low", "tokens_per_minute": 8000, "requests_per_minute": 30}, "output": {"formats": ["markdown", "csv", "bibtex"], "runs_dir": "outputs/runs", "citation_style": "ieee"}, "review": {"year_min": 2019, "max_papers": 10, "min_papers": 20, "max_iterations": 3, "coverage_threshold": 0.8, "grounding_threshold": 0.7}, "sources": {"enabled": ["openalex", "arxiv"], "max_per_source": 100}, "verifier": {"onnx_path": "data/models/verifier-onnx", "tokenizer": "microsoft/deberta-v3-small", "support_threshold": 0.7}, "retrieval": {"rrf_k": 60, "fusion": "rrf", "rerank": true, "dense_k": 30, "final_k": 12, "reranker": "data/models/reranker-mixed-onnx", "sparse_k": 30, "chunk_size": 1200, "chunk_overlap": 200}, "embeddings": {"model": "BAAI/bge-small-en-v1.5", "device": "cpu", "batch_size": 32}}	running	[]	{}	\N	2026-08-29 13:12:16.890756+05:30	\N
f033580e-e115-45e6-bc93-9aa542aa4844	t410_widened	How do multi-agent retrieval-augmented systems reduce hallucination in automated literature review?	{"llm": {"model": "openai/gpt-oss-20b", "provider": null, "cache_dir": "data/llm_cache", "max_tokens": 2048, "max_retries": 5, "temperature": 0.1, "planner_model": "openai/gpt-oss-20b", "reasoning_effort": "low", "tokens_per_minute": 8000, "requests_per_minute": 30}, "output": {"formats": ["markdown", "csv", "bibtex"], "runs_dir": "outputs/runs", "citation_style": "ieee"}, "review": {"year_min": 2019, "max_papers": 10, "min_papers": 20, "max_iterations": 3, "coverage_threshold": 0.8, "grounding_threshold": 0.7}, "sources": {"enabled": ["openalex", "arxiv"], "max_per_source": 100}, "verifier": {"onnx_path": "data/models/verifier-onnx", "tokenizer": "microsoft/deberta-v3-small", "support_threshold": 0.7}, "retrieval": {"rrf_k": 60, "fusion": "rrf", "rerank": true, "dense_k": 30, "final_k": 12, "reranker": "data/models/reranker-mixed-onnx", "sparse_k": 30, "chunk_size": 1200, "chunk_overlap": 200}, "embeddings": {"model": "BAAI/bge-small-en-v1.5", "device": "cpu", "batch_size": 32}}	completed	[{"name": "review.md", "path": "outputs\\\\runs\\\\t410_widened\\\\review.md", "bytes": 11310, "sha256": "bd0ff37fb245d6254e42cdf517e87ca24b5bc7da049585d6ef7ff1c5f63c91c4"}, {"name": "refs.bib", "path": "outputs\\\\runs\\\\t410_widened\\\\refs.bib", "bytes": 3058, "sha256": "1e2fdb2ba0d20df3c8dd80ed4c25eaf272d6e508a40843ef546d9c9def54c24f"}, {"name": "insights.csv", "path": "outputs\\\\runs\\\\t410_widened\\\\insights.csv", "bytes": 11953, "sha256": "60467933f4c4dafa6ce323504c81850cb24aa324695ac73cd04f1eb4b79d9ca7"}, {"name": "corpus.json", "path": "outputs\\\\runs\\\\t410_widened\\\\corpus.json", "bytes": 17139157, "sha256": "d9f1aa2ca052695e8228498e291724b7c454f0fd3f7998ebf70d0772e7dc1ad0"}, {"name": "claims.json", "path": "outputs\\\\runs\\\\t410_widened\\\\claims.json", "bytes": 20262, "sha256": "44b0b46053775577973b12e17c6b02f9b4b66fdd7773f9e1d780ed840cba0820"}, {"name": "config.json", "path": "outputs\\\\runs\\\\t410_widened\\\\config.json", "bytes": 1282, "sha256": "76d9a26a1b1a63f6d237ee9826e2535b2f8436afbd9c87f029d716678297190d"}]	{"papers": 8347, "insights": 10, "decisions": ["WRITE", "WRITE"], "iterations": 0, "dropped_claims": 0, "grounding_score": 1.0, "verified_claims": 17}	\N	2026-08-29 14:00:58.237859+05:30	2026-08-29 15:15:05.886459+05:30
\.


--
-- Name: artefact_scores artefact_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.artefact_scores
    ADD CONSTRAINT artefact_scores_pkey PRIMARY KEY (id);


--
-- Name: paper_scores paper_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_scores
    ADD CONSTRAINT paper_scores_pkey PRIMARY KEY (id);


--
-- Name: runs runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runs
    ADD CONSTRAINT runs_pkey PRIMARY KEY (id);


--
-- Name: runs runs_run_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runs
    ADD CONSTRAINT runs_run_id_key UNIQUE (run_id);


--
-- Name: artefact_scores uq_artefact_scores_run_artefact_reviewer; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.artefact_scores
    ADD CONSTRAINT uq_artefact_scores_run_artefact_reviewer UNIQUE (run_id, artefact, reviewer);


--
-- Name: paper_scores uq_paper_scores_run_paper_reviewer; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_scores
    ADD CONSTRAINT uq_paper_scores_run_paper_reviewer UNIQUE (run_id, paper_id, reviewer);


--
-- Name: ix_artefact_scores_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_artefact_scores_run_id ON public.artefact_scores USING btree (run_id);


--
-- Name: ix_paper_scores_doi; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_paper_scores_doi ON public.paper_scores USING btree (doi);


--
-- Name: ix_paper_scores_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_paper_scores_run_id ON public.paper_scores USING btree (run_id);


--
-- Name: ix_runs_artefacts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_runs_artefacts ON public.runs USING gin (artefacts);


--
-- Name: ix_runs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_runs_created_at ON public.runs USING btree (created_at DESC);


--
-- PostgreSQL database dump complete
--

\unrestrict Uxr0gMXIoGjXsdaFWARONqyAiYDeC6d96MUkEPr9k5UXi7dRMVJbCkB5nUgI0g9

