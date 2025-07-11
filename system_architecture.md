# AI-Powered Sales Agent System Architecture

```mermaid
graph TB
    %% External Services
    Slack[("Slack")] 
    Bing[Bing Web Search API]
    
    %% AWS Services
    API[{"API Gateway"}]
    Router[{"Lambda Router"}]
    Actions[{"Lambda Actions"}]
    Agent[{"Bedrock Agent<br/>Claude 3.5 Haiku"}]
    S3[("S3 Bucket")]
    RDS[("RDS Database")]
    VectorDB[("Vector Database")]
    DynamoDB[("DynamoDB")]
    CloudWatch[("CloudWatch")]
    
    %% Processing Components
    Reranker[{"Multi-step<br/>Retrieval Re-ranker"}]
    BriefGen[{"Brief Generation<br/>Module"}]
    PDFGen[{"PDF Generator<br/>WeasyPrint"}]
    Analytics[{"Analytics<br/>Processor"}]
    
    %% Data Stores
    TagDB[("Tag Database")]
    TemplateDB[("Template Database")]
    
    %% Slack Channels
    Planning[("#planning")]
    Manager[("#manager-desk")]
    
    %% Phase 1: Ingestion & Triggering
    Slack -->|"Slack Event"| API
    API -->|"Signature Verification"| Router
    Router -->|"Structured JSON"| Agent
    
    %% Phase 2: Core Agent Processing & RAG
    Agent -->|"detect_missing_fields()"| Router
    Agent -->|"search_tags()"| TagDB
    Agent -->|"Internal Knowledge Query"| VectorDB
    Agent -->|"External Knowledge Query"| Bing
    
    %% RAG Processing
    VectorDB --> Reranker
    Bing --> Reranker
    Reranker -->|"Re-ranked Results"| Agent
    
    %% Phase 3: Output Generation
    Agent -->|"Synthesized Output"| Router
    
    %% Phase 4: User Interaction via Slack
    Router -->|"Slack Block Kit"| Slack
    
    %% Phase 5: Handling User Feedback Actions
    Slack -->|"Action Buttons"| Actions
    Actions -->|"Update Status"| RDS
    Actions -->|"Modal Response"| Slack
    Actions -->|"Push to Planner"| BriefGen
    
    %% Phase 6: Brief Generation & Delivery
    BriefGen -->|"Planner Brief"| Planning
    BriefGen -->|"Manager Brief"| Manager
    BriefGen -->|"Markdown Template"| TemplateDB
    BriefGen -->|"PDF Generation"| PDFGen
    PDFGen -->|"Upload PDF"| S3
    S3 -->|"Pre-signed URL"| Planning
    S3 -->|"Pre-signed URL"| Manager
    
    %% Phase 7: Observability and Analytics
    Router -->|"Log Events"| CloudWatch
    Actions -->|"Log Events"| CloudWatch
    Agent -->|"Log Events"| CloudWatch
    CloudWatch -->|"Critical Errors"| DynamoDB
    
    %% Analytics Loop
    RDS -->|"Daily Batch"| Analytics
    Analytics -->|"User Feedback Stats"| CloudWatch
    CloudWatch -->|"QuickSight Dashboard"| Analytics
    
    %% Styling
    classDef external fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef aws fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef processing fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef storage fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef slack fill:#fce4ec,stroke:#ad1457,stroke-width:2px
    
    class Slack,Bing external
    class API,Router,Actions,Agent,S3,RDS,VectorDB,DynamoDB,CloudWatch aws
    class Reranker,BriefGen,PDFGen,Analytics processing
    class TagDB,TemplateDB storage
    class Planning,Manager slack
```

## System Components Overview

### External Services
- **Slack**: Primary user interface for sales team interactions
- **Bing Web Search API**: External knowledge retrieval

### AWS Services
- **API Gateway**: Entry point with signature verification
- **Lambda Router**: Message transformation and routing
- **Lambda Actions**: User feedback processing
- **Bedrock Agent**: AI processing with Claude 3.5 Haiku
- **S3**: PDF storage with pre-signed URLs
- **RDS**: Case status and data persistence
- **Vector Database**: Internal knowledge storage
- **DynamoDB**: Critical error storage
- **CloudWatch**: Comprehensive logging and monitoring

### Processing Components
- **Multi-step Retrieval Re-ranker**: Result ranking and synthesis
- **Brief Generation Module**: Report creation for different audiences
- **PDF Generator**: Markdown to PDF conversion
- **Analytics Processor**: User feedback analysis

### Data Flow Phases
1. **Ingestion**: Slack → API Gateway → Lambda Router
2. **Processing**: Agent with RAG (internal + external knowledge)
3. **Output**: Structured Slack messages with action buttons
4. **Feedback**: User actions processed by Lambda Actions
5. **Delivery**: Brief generation and PDF distribution
6. **Analytics**: Continuous monitoring and optimization loop 