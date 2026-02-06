# Specification Quality Validation

Reusable validation checklist for ensuring specification quality before planning.

## Content Quality Checks

- [ ] No implementation details (languages, frameworks, APIs)
- [ ] Focused on user value and business needs
- [ ] Written for non-technical stakeholders
- [ ] All mandatory sections completed

## Requirement Completeness Checks

- [ ] No [NEEDS CLARIFICATION] markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Success criteria are measurable
- [ ] Success criteria are technology-agnostic (no implementation details)
- [ ] All acceptance scenarios are defined
- [ ] Edge cases are identified
- [ ] Scope is clearly bounded
- [ ] Dependencies and assumptions identified

## Feature Readiness Checks

- [ ] All functional requirements have clear acceptance criteria
- [ ] User scenarios cover primary flows
- [ ] Feature meets measurable outcomes defined in Success Criteria
- [ ] No implementation details leak into specification

## Audit Mode Quality Checks (if --from-audit used)

- [ ] All key functions from audit are reflected in requirements
- [ ] Data models from audit are documented in Key Entities
- [ ] API contracts from audit are reflected in functional requirements
- [ ] Dependencies from audit are listed in Dependencies section
- [ ] Real code evidence is cited (file:line references)

## Validation Process

### Step 1: Run Check
Review the spec against each checklist item and determine pass/fail status.

### Step 2: Handle Results

**If all items pass**: Proceed to next phase (planning/implementation)

**If items fail (excluding [NEEDS CLARIFICATION])**:
1. List failing items and specific issues
2. Update spec to address each issue
3. Re-run validation (max 3 iterations)
4. If still failing, document issues and warn user

**If [NEEDS CLARIFICATION] markers remain**:
1. Extract all markers from spec
2. Keep only 3 most critical (scope > security > UX > technical)
3. Present options to user in structured format
4. Wait for responses and update spec
5. Re-run validation

## Common Reasonable Defaults (Don't Ask)

- Data retention: Industry-standard practices
- Performance targets: Standard web/mobile expectations
- Error handling: User-friendly messages with fallbacks
- Authentication: Session-based or OAuth2 for web apps
- Integration patterns: RESTful APIs unless specified

## Clarification Priority Order

1. Feature scope and boundaries
2. Security/privacy requirements
3. User experience decisions
4. Technical implementation details
