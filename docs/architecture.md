# Architecture Design Document

## Project Overview

This project is a scalable creator-intelligence platform powered by Retrieval-Augmented Generation (RAG). The system ingests YouTube videos and Instagram Reels, extracts transcripts and metadata, computes engagement analytics, stores semantic representations in a vector database, and allows users to perform conversational analysis through a streaming chat interface.

Unlike a traditional chatbot, this system combines:

* Structured metadata analysis
* Semantic transcript retrieval
* Engagement analytics
* Comparative reasoning
* Source-cited responses
* Multi-turn conversational memory

The architecture is designed to support:

* 2,000 creators/day
* Up to 10 videos per creator
* 20,000 video ingestions/day
* Low-cost retrieval
* Horizontal scalability

---

# High Level Architecture

```text
                     USER

                       │

                       ▼

              Next.js Frontend

                       │

                       ▼

                 FastAPI API

                       │

                       ▼

                 LangGraph

         ┌──────────┼──────────┐

         ▼          ▼          ▼

     Metadata   Retrieval   Analysis

         │          │          │

         ▼          ▼          ▼

     SQLite      Qdrant     Reasoning

         │          │

         ▼          ▼

    Metadata   Transcript Chunks

         │          │

         └──────┬───┘

                ▼

          Gemini Flash

                ▼

        Streaming Response
```

---

# Architectural Principles

The architecture is built around the following principles:

### 1. Separation of Concerns

Video ingestion and user querying are completely independent workflows.

Benefits:

* Better scalability
* Easier debugging
* Independent optimization
* Reduced user latency

### 2. Cost Efficiency

Embeddings and reranking use open-source models.

Only generation requires paid LLM inference.

Benefits:

* Near-zero retrieval cost
* Predictable scaling cost
* Reduced vendor lock-in

### 3. Retrieval Before Generation

The LLM never receives raw transcripts.

The system first:

* Retrieves evidence
* Filters evidence
* Structures evidence

Then generates an answer.

Benefits:

* Lower hallucination rate
* Better reasoning quality
* Lower token usage

---

# System Components

## Frontend Layer

Technology:

* Next.js
* React
* TailwindCSS
* Server Sent Events (SSE)

Responsibilities:

* Video URL submission
* Metadata visualization
* Video comparison dashboard
* Chat interface
* Streaming answer rendering
* Citation display

---

## Backend Layer

Technology:

* FastAPI

Responsibilities:

* API management
* LangGraph execution
* Authentication (future)
* Session management
* Streaming endpoints

Reason for selection:

* Async support
* Excellent Python ecosystem
* AI framework compatibility
* High throughput

---

# Ingestion Architecture

The ingestion workflow processes videos before they become searchable.

## Ingestion Graph

```text
Video URL

   ↓

Metadata Extraction

   ↓

Transcript Extraction

   ↓

Transcript Cleaning

   ↓

Hook Extraction

   ↓

Summary Generation

   ↓

Chunking

   ↓

Embedding Generation

   ↓

Qdrant Storage
```

---

## Metadata Extraction

Collected data:

* Video title
* Creator name
* Views
* Likes
* Comments
* Follower count
* Upload date
* Hashtags
* Duration

Additional metrics:

Engagement Rate

```text
(likes + comments) / views × 100
```

Stored separately for fast retrieval.

---

## Transcript Extraction Strategy

### Primary Method

YouTube Transcript API

Benefits:

* Fast
* Free
* Reliable

### Fallback Method

yt-dlp + Whisper

Benefits:

* Works without captions
* Supports Instagram Reels
* Supports any video source

---

## Hook Extraction

A hook is extracted during ingestion.

Stored:

* First 5 seconds
* First 50 words

This prevents repeated processing during comparison queries.

---

## Summary Generation

Each video receives:

* Semantic summary
* Key themes
* Main topics

Benefits:

* Faster retrieval
* Reduced token costs
* Improved scalability

---

# Chunking Strategy

Chunk Size:

```text
400 tokens
```

Overlap:

```text
50 tokens
```

Reasoning:

* Preserves semantic meaning
* Avoids context fragmentation
* Improves retrieval precision

Example:

```text
Chunk 1: 0–400

Chunk 2: 350–750

Chunk 3: 700–1100
```

---

# Embedding Layer

Model:

BAAI/bge-small-en-v1.5

Reasons:

* Open source
* Strong retrieval benchmarks
* Local inference
* Zero embedding API cost

Embedding Dimension:

```text
384
```

Generated once per chunk.

Never recomputed.

---

# Vector Database Layer

Technology:

Qdrant

Reasons:

* Production ready
* HNSW indexing
* Metadata filtering
* Open source
* Docker friendly

Stored Fields:

```json
{
  "video_id": "A",
  "chunk_id": "A_15",
  "timestamp": "00:04:30",
  "text": "...",
  "embedding": [...]
}
```

---

# Query Architecture

## Query Graph

```text
User Query

      ↓

Intent Router

      ↓

Query Rewrite

      ↓

Retrieval

      ↓

Reranking

      ↓

Context Builder

      ↓

Analysis Node

      ↓

Citation Builder

      ↓

Memory Update

      ↓

Streaming Generation
```

---

# Intent Routing

Supported intents:

### engagement

Example:

"What is the engagement rate?"

Uses metadata only.

No vector search.

---

### creator_info

Example:

"Who is the creator?"

Uses metadata only.

No vector search.

---

### hook_comparison

Example:

"Compare the hooks."

Uses hook metadata + transcript retrieval.

---

### general_comparison

Example:

"Why did Video A outperform Video B?"

Uses:

* Metadata
* Transcript retrieval
* Analysis node

---

# Retrieval Layer

Query is embedded using BGE.

Search:

Top 20 chunks

Retrieved from:

Qdrant HNSW index

---

# Reranking Layer

Model:

bge-reranker-v2-m3

Process:

```text
20 Retrieved Chunks

      ↓

Cross Encoder

      ↓

Top 5 Chunks
```

Benefits:

* Higher relevance
* Better answer quality
* Reduced hallucinations

---

# Context Builder

The system constructs structured context.

Example:

```json
{
  "video_a": {...},
  "video_b": {...},
  "engagement": {...},
  "chunks": [...]
}
```

Benefits:

* Better reasoning
* Consistent prompts
* Lower token usage

---

# Analysis Engine

The analysis node performs structured reasoning.

Computed metrics:

* Engagement difference
* Follower difference
* Duration difference
* Hook comparison
* Hashtag overlap

Example:

```json
{
  "engagement_gap": 4.2,
  "follower_gap": 54000,
  "duration_gap": 85
}
```

The LLM receives this data directly.

Benefits:

* More accurate comparisons
* Better reasoning quality

---

# Memory Architecture

Strategy:

Conversation Summary Memory

Not:

Conversation Buffer Memory

Reason:

Buffers grow infinitely.

Summaries remain bounded.

Stored:

* Prior conclusions
* User preferences
* Previous comparisons

Benefits:

* Lower token usage
* Better scalability

---

# Citation System

Every answer includes source references.

Example:

```text
Video A used a stronger curiosity hook.

Source:
Video A
Chunk A_12
Timestamp 04:31
```

Benefits:

* Transparency
* Trust
* Explainability

---

# Streaming Architecture

Method:

Server Sent Events (SSE)

Flow:

```text
LLM Token

     ↓

FastAPI Stream

     ↓

Frontend

     ↓

Immediate Rendering
```

Benefits:

* Better UX
* Lower perceived latency
* Simpler than WebSockets

---

# Scalability Strategy

Current Target:

* 2,000 creators/day
* 10 videos/creator
* 20,000 videos/day

---

## Scaling Phase 1

Current:

* Single Qdrant instance
* Single FastAPI deployment

---

## Scaling Phase 2

Add:

* Redis queue
* Background workers
* PostgreSQL

---

## Scaling Phase 3

Add:

* Multi-node Qdrant
* Kubernetes
* Worker autoscaling

---

# Cost Optimization Strategy

### Open Source Embeddings

Cost:

$0

---

### Open Source Reranking

Cost:

$0

---

### Self Hosted Vector Database

Cost:

$0 licensing

---

### Cached Transcript Processing

Video hash deduplication prevents:

* Re-embedding
* Re-transcription
* Duplicate storage

---

# Bottleneck Analysis

The primary bottleneck is NOT retrieval.

The primary bottleneck is:

Transcript Extraction

Reasons:

* Large audio files
* Whisper processing time
* External platform limitations

Mitigation:

* Transcript caching
* Background workers
* Video deduplication

---

# Future Improvements

* Hybrid BM25 + Dense Retrieval
* Redis Semantic Cache
* Multi-Level Retrieval
* Agentic Retrieval
* Multi-Video Group Analysis
* Creator Performance Forecasting

---

# Conclusion

This architecture separates ingestion, retrieval, reasoning, and generation into independent layers. The design minimizes cost, maximizes retrieval quality, supports conversational memory, and provides a clear path from a demo environment to a production-scale deployment handling thousands of creators per day.
