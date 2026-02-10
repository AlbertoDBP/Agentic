# Testing Specification Patterns

## Core Principle

Testing is integrated into implementation specs, not separated. Every implementation spec has a "Testing & Acceptance" section that defines:
1. Unit test requirements
2. Integration test scenarios
3. Acceptance criteria (testable)
4. Known edge cases
5. Performance/Reliability SLAs

This ensures developers and QA have a shared understanding of success before implementation starts.

## Unit Testing Patterns

### Basic Pattern

For each public function/method, specify:

```markdown
### Unit Test Requirements

test_[component_name]_[function_name]:
  - **Normal case**: 
    Input: [specific valid input]
    Expected: [specific expected output/behavior]
  
  - **Edge case 1 - Empty/Null**:
    Input: [empty or null input]
    Expected: [should raise ValueError or return default]
  
  - **Edge case 2 - Boundary**:
    Input: [value at boundary]
    Expected: [specific behavior at limit]
  
  - **Error case - Invalid type**:
    Input: [wrong type]
    Expected: [TypeError raised with message]
  
  - **Error case - Out of range**:
    Input: [value outside valid range]
    Expected: [ValueError raised]
```

### Example: Agent Routing Component

```markdown
### Unit Test Requirements

**test_agent_router_select_agent**:
- **Normal case**: 
  Input: Request with category="evaluation"
  Expected: Returns RoutingDecision with agent_id="evaluator"
  
- **Edge case - Unknown category**:
  Input: Request with category="unknown_type"
  Expected: Raises UnknownCategoryError with log entry
  
- **Edge case - Empty request**:
  Input: Empty request object
  Expected: Raises ValueError("request cannot be empty")
  
- **Error case - Circular dependency**:
  Input: Agent lookup results in self-reference
  Expected: Raises CircularReferenceError, prevents infinite loop
  
- **Timeout case**:
  Input: Agent registry lookup takes > 5s
  Expected: Raises TimeoutError, returns fallback agent

**test_agent_router_calculate_confidence**:
- **Normal case**:
  Input: Request with 3 matching agents, confidence scores [0.95, 0.80, 0.60]
  Expected: Returns 0.95 (highest confidence)
  
- **Tie case**:
  Input: Two agents with identical confidence score 0.85
  Expected: Returns first match, logs tie resolution
```

## Integration Testing Patterns

Integration tests verify components work together correctly.

### Pattern: Component to Component

```markdown
### Integration Test Scenarios

**Scenario: Request flows from Router → Evaluator → Orchestrator**
- Setup: Initialize Router, Evaluator, Orchestrator in test harness
- Input: Request object with evaluation task
- Flow:
  1. Router.select_agent(request) returns evaluator_agent_id
  2. Evaluator.evaluate(data) returns EvaluationResult
  3. Orchestrator.process(evaluation_result) updates state
- Expected Output: Final result matches expected computation
- Verification: Check each component received correct data in order

**Scenario: Error in downstream component propagates correctly**
- Setup: Configure Evaluator to fail under specific condition
- Input: Request that triggers evaluation failure
- Flow: Error in Evaluator should be caught by Orchestrator
- Expected: Orchestrator returns error response, logs failure, no crash
- Verification: Error tracking includes full call stack

**Scenario: State consistency across components**
- Setup: Initialize shared state object
- Process:
  1. Component A updates state key "status" to "processing"
  2. Component B reads same state, sees update
  3. Component C updates same key to "complete"
  4. Verify all components see final state
- Verification: No race conditions, consistent view of state
```

### Pattern: API Integration

```markdown
### Integration Test Scenarios

**Scenario: Component calls external API successfully**
- Setup: Mock external API with known response
- Input: Request requiring API call
- Flow:
  1. Component prepares API request with correct headers/auth
  2. Component sends request with timeout X
  3. Component receives response and parses result
- Expected: Correct data extracted from response
- Verification: API was called with expected parameters

**Scenario: External API timeout handling**
- Setup: Mock API to timeout after 2s
- Input: Request to component with 5s timeout threshold
- Flow: Component call to API times out
- Expected: Component catches timeout, returns error response after 2s (not 5s)
- Verification: Request completed in < 3s, error logged

**Scenario: External API rate limiting**
- Setup: Mock API to return 429 (Too Many Requests)
- Process:
  1. First request succeeds
  2. Second request immediately after gets 429
  3. Component should retry with backoff
- Expected: Component waits before retry, second attempt succeeds
- Verification: Retry backoff strategy working (exponential, jitter)
```

## Acceptance Criteria Pattern

Acceptance criteria are **testable, specific, measurable** requirements that define success.

### Formula
`When [condition], [verify that] [expected outcome]`

### Good Examples

**Good - Specific and testable**:
- `When payload contains valid JSON, endpoint returns 200 OK within 500ms`
- `When user has "admin" role, API returns records; without role, returns 403 Forbidden`
- `When input exceeds 1GB, system chunks into 10MB pieces and processes sequentially`
- `When upstream service is unavailable, component returns error code 503 and logs retry attempt`

**Bad - Vague and not testable**:
- `Component should work correctly` ✗
- `API should be fast` ✗
- `Error handling should be robust` ✗
- `System should handle edge cases` ✗

### Format in Specifications

```markdown
### Acceptance Criteria (Testable)

- `When valid agent request received, component routes to correct agent within 100ms`
- `When agent list is empty, component returns DefaultAgent and logs warning`
- `When two agents match equally, component selects first in ordered list consistently`
- `Over 100 runs with identical input, routing decision varies < 1% (acceptable due to randomization)`
- `When upstream service timeout (>5s), component fails gracefully and returns error response`
```

## Edge Cases Pattern

Document all known edge cases and expected behavior.

### Format

```markdown
### Known Edge Cases & Failure Modes

| Edge Case | Condition | Expected Behavior | How Handled |
|-----------|-----------|------------------|---|
| Empty input | Input list is empty | Return empty result | Input validation raises ValueError |
| Null values | Field is None/null | Skip field or use default | Check for None before processing |
| Type mismatch | String instead of int | Type error | Explicit type checking with error message |
| Out of range | Value > max | Clamp to max or error | Document max and enforce |
| Dependency failure | Required service down | Degrade gracefully | Return error, use fallback, log |
| Resource exhaustion | Memory/CPU maxed | Throttle or fail | Monitor and alert, graceful shutdown |
| Timeout | Operation takes too long | Return partial result or error | Configurable timeout, logging |
| Race condition | Concurrent access | Data consistency | Locking or atomic operations |
| Missing dependency | Required field absent | Use default or error | Schema validation upfront |
```

### Example: Agent Component

```markdown
### Known Edge Cases & Failure Modes

| Scenario | Condition | Expected | Handling |
|----------|-----------|----------|----------|
| Agent hallucination | LLM generates incorrect data | Return low confidence score | Confidence threshold filtering |
| Context window exceeded | Input + context > token limit | Truncate context | Drop oldest messages, log warning |
| Conflicting signals | Multiple data sources disagree | Agent escalates decision | Escalation to human review |
| Circular reasoning | Agent references previous reasoning | Detect loop, stop | Maintain reasoning history, detect patterns |
| Ambiguous instruction | Request could be interpreted multiple ways | Ask for clarification | Return clarification request |
| No matching agent type | Request type unrecognized | Return error | Log unrecognized type, suggest closest match |
```

## Performance & Reliability SLAs Pattern

Define measurable performance targets.

### Format

```markdown
## Performance & Reliability SLAs

**Latency**:
- P95 latency: < 500ms (95% of requests)
- P99 latency: < 2000ms (99% of requests)
- Maximum latency: < 10s (hard limit, timeouts after)

**Throughput**:
- Minimum: 100 requests/second
- Maximum: 10,000 requests/second
- Burst capacity: 15,000 requests/second for up to 1 minute

**Error Rate**:
- Normal operation: < 0.1% errors
- Degraded mode: < 1% errors
- Critical error: 0 allowed (system shutdown if exceeded)

**Availability**:
- Target uptime: 99.9% (8.76 hours downtime/year)
- Maintenance window: 2 hours/month (scheduled, off-peak)

**Resource Usage**:
- Memory: < 500MB per instance
- CPU: < 80% average
- Disk: < 90% usage
```

### Example: Data Processing Component

```markdown
## Performance & Reliability SLAs

**Processing Speed**:
- Single record: < 100ms
- Batch of 1000: < 5 seconds
- Large batch (10k+): Linear scaling, < 0.01s per record

**Reliability**:
- Data loss: 0% (all data persisted before processing)
- Duplicate handling: < 0.01% duplicates processed twice
- Failure recovery: Automatic retry up to 3 times with exponential backoff

**Concurrency**:
- Up to 100 concurrent requests
- Graceful degradation beyond capacity
- Queue depth monitoring with alerts
```

## Agent-Specific Testing Pattern

For agentic components, add specific testing patterns:

### Behavioral Consistency

```markdown
### Agent Behavioral Testing

**Determinism Testing** (when applicable):
- Same input, same context should produce consistent output
- Variance tolerance: [specify allowable difference]
- Testing: Run identical request 50 times, measure variance
- Example: Agent evaluation task run 50x should have < 5% variance in decision

**Confidence Scoring**:
- Agent should score own confidence appropriately
- Test cases:
  - Clear decision: confidence > 0.95
  - Ambiguous decision: confidence 0.50-0.80
  - No data: confidence = 0
- Verify: Confidence scores correlate with actual accuracy

**Reasoning Quality**:
- Agent should explain reasoning, not just return answer
- Verify: Explanation logically supports conclusion
- Test: Remove explanation, would conclusion still be obvious?

**Hallucination Detection**:
- Agent should not invent data not present in input
- Test: Inject false information into context, verify agent doesn't cite it
- Verify: All claims traceable to input data or knowledge base

**Mode Switching**:
- Agent should recognize when it lacks information
- Should escalate to human review vs. proceeding
- Test: Introduce unknown scenario, verify escalation triggered
```

### Failure Mode Testing for Agents

```markdown
### Agent Failure Modes

**Handling Conflicting Information**:
- When data sources disagree, agent should:
  - Acknowledge conflict
  - Lower confidence score
  - Escalate if critical decision
  - Log which source was prioritized and why

**Token Exhaustion**:
- If context window approaches limit, agent should:
  - Summarize before adding new data
  - Drop least relevant context
  - Alert that truncation occurred
  - Not hallucinate due to token pressure

**Instruction Following**:
- Agent should follow explicit instructions even if suboptimal
- Test: Give instruction that conflicts with training
- Verify: Agent follows explicit instruction, logs conflict
```

## Validation Checklist for Testing Specs

When reviewing a testing specification, verify:

- [ ] All public methods have unit test requirements
- [ ] Edge cases are explicitly listed, not just implied
- [ ] Integration scenarios cover happy path AND error paths
- [ ] Acceptance criteria are testable (not vague)
- [ ] Acceptance criteria use specific numbers/thresholds
- [ ] SLAs are defined with clear metrics
- [ ] Performance targets are realistic and measurable
- [ ] Failure modes are documented with expected behavior
- [ ] Agent-specific tests included (if applicable)
- [ ] Dependencies on other components identified
- [ ] Timeout and concurrency scenarios covered

## Testing Execution

### By Development Team

1. Create test file structure matching implementation spec requirements
2. Write unit tests first (test-driven development preferred)
3. Run tests during development, keep passing
4. Document any edge cases discovered during implementation

### By QA Team

1. Review acceptance criteria with developers
2. Create test cases for each acceptance criterion
3. Execute integration tests with full system
4. Load test against SLA targets
5. Document any deviations and root causes

### By Platform Team

1. Monitor SLA compliance in production
2. Alert when approaching thresholds
3. Collect metrics for baseline optimization
4. Feed learnings back into future specifications
