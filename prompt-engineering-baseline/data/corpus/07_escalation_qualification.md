# Escalation Policy and Sales Qualification — Full Reference

## Support Escalation Policy

### L1 → L2 Escalation Criteria
Escalate to L2 support if ANY of the following:
- Issue unresolved after 2 full diagnostic cycles
- Error rate >5% sustained for more than 15 minutes
- Data loss or data corruption suspected
- Security incident suspected (unauthorised access, key compromise)
- Customer impact: >100 devices affected simultaneously
- SLA breach imminent or already breached

### L2 → L3 / Engineering Escalation Criteria
Escalate to L3 Engineering if ANY of the following:
- L2 cannot reproduce or resolve within 4 hours
- Systemic issue affecting multiple customers
- Bug confirmed in API or SDK
- Infrastructure incident (not customer configuration)

### Escalation Package Required
When escalating, always include:
- case_id: support case identifier
- affected_service: Directions | Distance Matrix | Autocomplete | Reverse Geocode | Tracking | Geofencing
- error_codes[]: list of HTTP error codes observed
- steps_taken[]: diagnostic steps already completed
- impact_assessment: number of devices/users affected, business impact
- request_id: from X-Request-Id response header (if available)
- timestamps: when issue started, frequency, pattern

### Sales Escalation Criteria
Escalate to Solutions Engineer if ANY of the following:
- Custom integration requirements beyond standard SDK
- Accuracy requirements below 1 metre (UWB evaluation needed)
- More than 10,000 concurrent devices
- Data residency or compliance requirements (GDPR, HIPAA, SOC2)
- Custom SLA negotiation required
- Proof of concept or pilot programme requested

Escalate to Legal/Commercial if:
- Custom SLA negotiation
- DPA (Data Processing Agreement) needed
- Volume discount negotiation above standard tiers
- White-label or OEM licensing

## Sales Qualification — BANT+ Framework

### Budget
- Confirmed budget range or approval process?
- Is budget approved or still in planning?
- Decision timeline for budget approval?
- Current spend on location services (if any)?

### Authority
- Is the contact the decision-maker or an influencer?
- Who else is involved in the technical decision?
- Who signs the commercial agreement?
- Is procurement or legal involved?

### Need
- Primary use case: fleet tracking | asset tracking | indoor positioning | delivery routing | address search | geocoding?
- Current solution and pain points?
- Must-have vs nice-to-have features?
- Integration with existing systems?

### Timeline
- Go-live target date?
- Pilot or proof-of-concept planned?
- Procurement lead time?
- Implementation resource available?

### Technical (BANT+)
- Platform: iOS | Android | Web | Server-side?
- Expected device count (simultaneous)?
- Expected monthly API call volume?
- Accuracy requirement: city | street | metre | sub-metre?
- Integration method: REST | SDK | WebSocket?
- Existing tech stack?

### Compliance (BANT+)
- Data residency requirements (EU/US/APAC)?
- GDPR compliance needed?
- Industry regulations: HIPAA | SOC2 | ISO27001 | other?
- Data retention requirements?

## Discovery Questions (9 Standard)
1. What is the primary use case for location services?
2. How many devices or assets will be tracked simultaneously?
3. What accuracy level is required — city, street, metre, or sub-metre?
4. What platforms need to be supported — iOS, Android, Web, or server-side?
5. Are there existing systems to integrate with?
6. What is the expected monthly API call volume?
7. Are there data residency or compliance requirements?
8. What is the target go-live date?
9. Who else is involved in the technical and commercial decision?

## Ownership and Next Actions

### Sales Ownership Matrix
| Situation | Owner | Next Action |
|-----------|-------|-------------|
| Standard qualification | Account Executive | Send capability summary and pricing |
| Custom integration needed | Solutions Engineer | Schedule technical discovery call |
| >10K devices | Solutions Engineer | Enterprise scoping session |
| Compliance requirements | Solutions Engineer + Legal | DPA review and compliance checklist |
| Budget not confirmed | Account Executive | Follow up with economic buyer |
| Pilot requested | Solutions Engineer | Define pilot scope and success criteria |

### Support Ownership Matrix
| Situation | Owner | Next Action |
|-----------|-------|-------------|
| Standard diagnostic | L1 Support | Run 6-step diagnostic checklist |
| Unresolved after 2 cycles | L2 Support | Escalate with full case package |
| Error rate >5% >15min | L2 Support | Immediate escalation |
| Data loss suspected | L2 Support + Engineering | Emergency escalation |
| Security incident | Security Team | Immediate escalation, key rotation |
| Bug confirmed | L3 Engineering | File bug report, provide workaround |
