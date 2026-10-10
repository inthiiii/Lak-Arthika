# System Context

```mermaid
flowchart LR
    A[Official price sources] --> D[Ingestion pipeline]
    B[Economic indicators] --> D
    C[Weather and external data] --> D

    D --> E[Raw immutable storage]
    E --> F[Validation and standardization]
    F --> G[Analytical data store]
    G --> H[Feature pipeline]

    H --> I[Forecasting models]
    H --> J[Economic graph]
    H --> K[Scenario simulator]

    I --> L[LakArthika API]
    J --> L
    K --> L

    L --> M[Public application]
    L --> N[Government console]
    L --> O[Enterprise tools]
    L --> P[Geographic map]

    Q[Monitoring] --> D
    Q --> I
    Q --> L
