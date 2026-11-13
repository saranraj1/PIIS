# ADR-0001: Start with a modular monolith

- **Status:** Accepted
- **Decision:** Use one deployable application with strict internal module boundaries.
- **Context:** Early research scope is uncertain; independent microservices would add deployment and observability complexity before workload is known.
- **Consequences:** Easier local testing and refactoring; modules must avoid circular dependencies and communicate through explicit interfaces. Extract services only with evidence of scaling/isolation need.
