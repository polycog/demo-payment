# Problem Statement and Opportunity

## Problem statement

### How self-service banking works today

Customer banking operations encompass a wide variety of self-service tasks, such as reviewing loan payment plans, adjusting payment amounts or dates, and updating payment methods. Existing digital solutions rely on web or mobile interfaces that force users to navigate complex UI hierarchies, locate deeply nested menu options, and interpret specialized financial jargon. For example, consider a customer attempting to defer a loan payment or adjust their installment schedule due to an unexpected shift in payday. In a traditional mobile or web banking interface, the user typically must:

- Navigate through multiple nested menus and account overview screens to locate buried "Loan Services" or "Payment Settings" sections.
- Interpret specialized financial jargon (such as "principal adjustments," "amortization shifts," or "interest capitalization rules").
- Fill out a rigid static form that often lacks the flexibility to handle nuanced requests, resulting in validation errors or forcing the user to drop off and call customer support.

### What customers need

An autonomous agent eliminates this friction by allowing users to express their intent in natural language (e.g., *"Can I move my upcoming payment to next Friday?"*).

## Opportunity and challenge

Agents can transform the customer experience by using reasoning to translate natural customer requests into accurate API actions. However, to succeed in financial services, these agents must balance flexibility with strict adherence to bank policies and standard operating procedures. For instance, the bank may impose restrictions on how much a customer can adjust their payment or how far in advance they can modify their schedule. An agent must enforce these policies absolutely. A more complex requirement is enforcing [Strong Customer Authentication](https://en.wikipedia.org/wiki/Strong_customer_authentication) only when necessary, such as for high-risk or high-value transactions, while automatically applying exemptions for low-value transactions to minimize user friction.

## Impact

By deploying an intelligent, policy-aware assistant, banks can reduce customer drop-off rates, lower operational costs, and deliver a seamless user experience.

## Technical approach

See [the technical approach](approach.md) for how an agent with cognition inside meets this challenge.
