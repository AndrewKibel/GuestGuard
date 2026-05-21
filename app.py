#Page setup and app description
import streamlit as st
from openai import OpenAI
import json

st.title("GuestGuard")
st.subheader("Hybrid QA for AI Guest Messaging in Short-Term Rentals")
st.write("GuestGuard evaluates whether an AI-generated guest response is accurate, safe, "
         "SOP-compliant, and ready to send. It compares the guest message, property rules, "
         "and AI draft response to identify risky promises, missed policy details, escalation needs, "
         "and upsell opportunities.")
st.info(
    "Prototype note: GuestGuard uses a hybrid approach. The rule-based evaluator provides "
    "transparent guardrails for known high-risk situations, while the optional LLM evaluator "
    "can handle more flexible language and nuanced SOP interpretation.")

#Sidebar controls for optional LLM mode
st.sidebar.title("GuestGuard")
openaiApiKey = st.sidebar.text_input("Open AI API Key", type = "password", help = "Only needed if you want to run the optional LLM evaluator.")
runLLM = st.sidebar.checkbox("Run optional LLM evaluator")

#This dictionary stores the built-in demo scenarios
#Each scenario name points to three pieces of text: guest message, property rules, and AI draft response
scenarios = {
    "Custom": {
        "guest": "",
        "rules": "",
        "response": ""
    },
    "Early check-in + pet": {
        "guest": "Hi, we’re arriving around 1 PM. Can we check in early? Also, we’re bringing our dog — that’s okay, right?",
        "rules": "Check-in is 4 PM. Early check-in may be available for $35 only if cleaning is complete. Dogs under 25 lbs are allowed with a $75 pet fee. Cats are not allowed. Do not promise early check-in unless cleaning status is confirmed.",
        "response": "Hi! Yes, checking in at 1 PM is totally fine, and bringing your dog is no problem. We’re excited to host you!"
    },
    "Guest locked out": {
        "guest": "We just arrived and the door code is not working. We’re stuck outside with our kids.",
        "rules": "If a guest reports an access issue, broken lock, or being locked out, escalate immediately to the property manager. Do not tell the guest to wait more than 10 minutes.",
        "response": "Sorry about that. Please try again in 30 minutes and let us know if it still does not work."
    },
    "Refund request": {
        "guest": "The Wi-Fi was down last night. Can we get a refund for one night?",
        "rules": "Do not promise refunds or credits without manager approval. For refund requests, apologize, acknowledge the issue, and escalate to the property manager.",
        "response": "Sorry about the Wi-Fi issue. We can refund you for one night after your stay."
    },
    "Parking question": {
        "guest": "Where should we park when we arrive?",
        "rules": "Guests should park in spot 14. Street parking is allowed overnight except Tuesdays from 8 AM to 11 AM. Do not park in spots 1 through 13 because those belong to residents.",
        "response": "You can park in spot 14. Please avoid spots 1 through 13 because those are reserved for residents."
    },
    "Late checkout": {
        "guest": "Could we check out at noon instead of 10 AM?",
        "rules": "Checkout is 10 AM. Late checkout may be available for $30 only if there is no same-day guest arriving. Do not confirm late checkout until the calendar is checked.",
        "response": "Yes, noon checkout is totally fine. Enjoy your morning!"
    }
}

#User inputs
scenarioName = st.selectbox("Load Sample Scenario", list(scenarios.keys()))
selectedScenario = scenarios[scenarioName]

guestMessage = st.text_area("Guest Message", value = selectedScenario["guest"], height = 100)
propertyRules = st.text_area("Property SOP/Rules", value = selectedScenario["rules"], height = 150)
aiResponse = st.text_area("AI Draft Response", value = selectedScenario["response"], height = 120)

#Helper function to return true if a word is in a certain list, helpful for response keywords
def hasAny(text, keywords):
    return any(keyword in text for keyword in keywords)

#Rule-based prototype evaluator, comparing what the guest asked, what the property rules say, and what the AI draft response says
#Detects common short-term rental risk categories such as access issues, refunds, early check-in, late checkout, pet policies, parties/events, parking issues, safety concerns, and irrelevant responses
#Returns a dictionary consisting of a score, decision, flags, issue types, risk breakdown upsell opportunities, and a suggested better response
def evaluateResponse(guestMessage, propertyRules, aiResponse):

    guest_lower = guestMessage.lower()
    rules_lower = propertyRules.lower()
    response_lower = aiResponse.lower()

    score = 100
    flags = []
    upsells = []
    issueTypes = []
    decisionReasons = []
    decision = "Safe to Send"
    suggestedResponse = "The response looks reasonable based on the current rules."

    riskBreakdown = {
        "Accuracy": 100,
        "SOP Compliance": 100,
        "Escalation Safety": 100,
        "Guest Experience": 100,
        "Revenue Opportunity": 100
    }

    def addIssue(flag, issueType, scorePenalty, categoryPenalties, reason=None):
        nonlocal score, decision

        score -= scorePenalty
        flags.append(flag)

        if issueType not in issueTypes:
            issueTypes.append(issueType)

        if reason:
            decisionReasons.append(reason)

        for category, penalty in categoryPenalties.items():
            riskBreakdown[category] = max(riskBreakdown[category] - penalty, 0)

        if decision != "Escalate Immediately":
            decision = "Review Before Sending"

    # General safety / emergency check
    safetyKeywords = [
        "snake", "animal", "animals", "danger", "dangerous", "unsafe", "emergency",
        "police", "fire", "hurt", "injured", "blood", "break in", "intruder",
        "smoke", "gas", "leak", "flood", "electrical", "sparks"
    ]

    casualBadResponseKeywords = [
        "cool", "lol", "haha", "okay", "fine", "funny", "no worries", "all good",
        "nice", "awesome"
    ]

    if hasAny(guest_lower, safetyKeywords) or hasAny(rules_lower, safetyKeywords):
        if hasAny(response_lower, casualBadResponseKeywords):
            addIssue(
                "The AI response appears casual or irrelevant despite a safety-sensitive guest issue.",
                "Safety / Emergency",
                45,
                {
                    "Escalation Safety": 50,
                    "SOP Compliance": 35,
                    "Guest Experience": 35,
                    "Accuracy": 30
                },
                "The guest reported a potentially unsafe situation, but the AI response did not follow the SOP or take the issue seriously."
            )
            decision = "Escalate Immediately"
            suggestedResponse = (
            "I'm sorry—please exit the property immediately and move to a safe location. "
            "We are escalating this right away and contacting the appropriate emergency support according to the property SOP."
            )
    
    # General relevance check: catches nonsense replies that ignore the guest's actual issue
    importantGuestWords = []

    for word in guest_lower.replace(".", "").replace(",", "").replace("!", "").split():
        if len(word) > 4 and word not in ["there", "their", "about", "would", "could", "should", "hello", "walked"]:
            importantGuestWords.append(word)

    matches = 0
    for word in importantGuestWords:
        if word in response_lower:
            matches += 1

    if len(importantGuestWords) >= 3 and matches == 0:
        addIssue(
            "The AI response appears unrelated to the guest's message.",
            "Irrelevant Response",
            30,
            {
                "Accuracy": 35,
                "Guest Experience": 25,
                "SOP Compliance": 20
            },
            "The AI draft does not appear to address the main issue raised by the guest."
        )

        if decision != "Escalate Immediately":
            decision = "Review Before Sending"

    # High-risk access issue: guest may be locked out
    if (
        "locked out" in guest_lower
        or "door code" in guest_lower
        or "can't get in" in guest_lower
        or "cannot get in" in guest_lower
        or ("not working" in guest_lower and "door" in guest_lower)):
        addIssue(
            "Access issue detected: guest may be unable to enter the property.",
            "Escalation",
            40,
            {
                "Escalation Safety": 45,
                "Guest Experience": 25,
                "SOP Compliance": 20
            },
            "The guest may be locked out, so the response should be escalated immediately."
        )
        flags.append("SOP-sensitive issue: access problems should be escalated immediately.")
        decision = "Escalate Immediately"
        suggestedResponse = (
            "I'm sorry about that—we’ll help right away. I’m escalating this immediately "
            "to the property manager so we can get you inside as soon as possible. "
            "Please stay near the entrance and keep your phone available."
        )

    # Refunds should not be promised automatically
    if "refund" in guest_lower or "credit" in guest_lower:
        if "refund" in response_lower or "credit" in response_lower:
            addIssue(
                "Refund or credit was discussed. These requests usually need manager approval.",
                "Refund/Payment Risk",
                30,
                {
                    "SOP Compliance": 35,
                    "Accuracy": 20,
                    "Escalation Safety": 20
                },
                "The AI discussed a refund or credit even though the SOP says manager approval is required."
            )
            suggestedResponse = (
                "I'm sorry about the issue. I’ll pass this along to the property manager "
                "for review, and we’ll follow up with you as soon as possible."
            )

    # Early check-in should not be promised if it depends on cleaning or availability
    if "early" in guest_lower or "1 pm" in guest_lower or "1pm" in guest_lower:
        if "cleaning" in rules_lower or "available" in rules_lower:
            upsells.append("Possible early check-in upsell.")
            if "yes" in response_lower or "totally fine" in response_lower or "no problem" in response_lower:
                addIssue(
                    "Early check-in was promised without confirming cleaning status or availability.",
                    "Early Check-In",
                    25,
                    {
                        "SOP Compliance": 30,
                        "Accuracy": 20,
                        "Revenue Opportunity": 15
                    },
                    "The AI promised early check-in even though the SOP says cleaning status or availability must be confirmed first."
                )
                if "Upsell Opportunity" not in issueTypes:
                    issueTypes.append("Upsell Opportunity")
                suggestedResponse = (
                    "Early check-in may be available if cleaning is completed in time. "
                    "Once we confirm the unit is ready, we’ll let you know. "
                    "If available, early check-in can be added for the listed fee."
                )

    # Late checkout should not be promised if it depends on calendar availability
    if "late checkout" in guest_lower or "check out" in guest_lower or "checkout" in guest_lower or "noon" in guest_lower:
        if "same-day" in rules_lower or "calendar" in rules_lower or "available" in rules_lower:
            upsells.append("Possible late checkout upsell.")
            if "yes" in response_lower or "totally fine" in response_lower or "no problem" in response_lower:
                addIssue(
                    "Late checkout was confirmed without checking the calendar or same-day guest status.",
                    "Late Checkout",
                    25,
                    {
                        "SOP Compliance": 30,
                        "Accuracy": 20,
                        "Revenue Opportunity": 15
                    },
                    "The AI confirmed late checkout even though the SOP says calendar availability must be checked first."
                )
                if "Upsell Opportunity" not in issueTypes:
                    issueTypes.append("Upsell Opportunity")
                suggestedResponse = (
                    "Late checkout may be available if there is no same-day guest arriving. "
                    "We’ll check the calendar and confirm as soon as possible. "
                    "If available, late checkout can be added for the listed fee."
                )

    # Pet policy checks
    if "dog" in guest_lower or "pet" in guest_lower or "cat" in guest_lower:
        if "fee" in rules_lower and "fee" not in response_lower:
            addIssue(
                "Pet fee appears in the SOP but was not mentioned in the AI response.",
                "Pet Policy",
                15,
                {
                    "SOP Compliance": 20,
                    "Accuracy": 15,
                    "Revenue Opportunity": 10
                },
                "The AI missed the pet fee, which could create confusion or lost revenue."
            )

        if "25" in rules_lower and "25" not in response_lower:
            addIssue(
                "Pet weight requirement appears in the SOP but was not mentioned in the AI response.",
                "Pet Policy",
                10,
                {
                    "SOP Compliance": 15,
                    "Accuracy": 10
                },
                "The AI did not mention the pet weight requirement from the SOP."
            )

        if "cat" in guest_lower and "cats are not allowed" in rules_lower:
            addIssue(
                "Guest mentioned a cat, but the SOP says cats are not allowed.",
                "Pet Policy",
                25,
                {
                    "SOP Compliance": 30,
                    "Accuracy": 25,
                    "Guest Experience": 10
                },
                "The guest mentioned a cat, but the property rules do not allow cats."
            )
            suggestedResponse = (
                "Dogs under the listed weight limit are allowed with the pet fee, "
                "but unfortunately cats are not allowed at this property."
            )

    # Party/event checks
    partyKeywords = ["party", "event", "friends over", "birthday", "gathering", "dinner and music", "music", "outside guests", "people over"]

    if any(keyword in guest_lower for keyword in partyKeywords):
        if "no parties" in rules_lower or "parties are not allowed" in rules_lower or "gatherings are allowed" not in rules_lower:
            if "yes" in response_lower or "fine" in response_lower or "allowed" in response_lower or "sounds fine" in response_lower or "okay" in response_lower:
                addIssue(
                    "The AI response may allow a party, event, or outside gathering even though the SOP prohibits it.",
                    "House Rules",
                    35,
                    {
                        "SOP Compliance": 40,
                        "Accuracy": 25,
                        "Guest Experience": 10
                    },
                    "The AI may have approved a gathering or outside guests even though the house rules prohibit parties or events."
                )
                suggestedResponse = (
                    "Thanks for checking. Unfortunately, parties, events, and gatherings with outside guests "
                    "are not allowed at this property. Only registered guests may be on the property, "
                    "in accordance with the house rules."
                )

    # Parking check
    if "park" in guest_lower or "parking" in guest_lower:
        if "spot" in rules_lower and "spot" not in response_lower:
            addIssue(
                "Guest asked about parking, but the AI response did not include the specific parking spot.",
                "Parking",
                15,
                {
                    "Accuracy": 20,
                    "Guest Experience": 15
                },
                "The guest asked about parking, but the AI response left out the specific parking spot."
            )

    # Keep score from going below zero
    score = max(score, 0)

    # If no flags were found, keep decision positive
    if len(flags) == 0:
        decision = "Safe to Send"

    if len(decisionReasons) == 0:
        decisionReasons.append("No major issues were detected based on the current rules.")

    return {
        "score": score,
        "decision": decision,
        "flags": flags,
        "upsells": upsells,
        "issueTypes": issueTypes,
        "decisionReasons": decisionReasons,
        "riskBreakdown": riskBreakdown,
        "suggestedResponse": suggestedResponse
    }

#Creates the structured propmpt to send to the optional LLM evaluator
#Prompt asks LLM to evaluate the AI draft response using the same categories as the rule-based evaluator
def createLLMPrompt(guestMessage, propertyRules, aiResponse):
    return f"""
You are an AI QA evaluator for a short-term rental guest messaging platform.

Your job is to evaluate whether an AI-generated guest response is safe, accurate,
SOP-compliant, helpful, and ready to send to a guest.

Evaluate the response using these categories:
1. Accuracy: Does the response correctly answer the guest based on the property SOP?
2. SOP Compliance: Does the response follow all property rules and restrictions?
3. Escalation Safety: Should this have been escalated to a human?
4. Guest Experience: Is the response polite, clear, and helpful?
5. Revenue Opportunity: Did the response miss an opportunity for an approved upsell?

Guest Message:
{guestMessage}

Property SOP / Rules:
{propertyRules}

AI Draft Response:
{aiResponse}

Return your evaluation in this JSON structure:

{{
  "overallScore": 0-100,
  "decision": "Safe to Send" or "Review Before Sending" or "Escalate Immediately",
  "decisionReason": "Brief explanation",
  "issueTypes": ["Example Issue Type"],
  "riskBreakdown": {{
    "Accuracy": 0-100,
    "SOP Compliance": 0-100,
    "Escalation Safety": 0-100,
    "Guest Experience": 0-100,
    "Revenue Opportunity": 0-100
  }},
  "flags": ["Specific problems found"],
  "upsellOpportunities": ["Possible approved upsells"],
  "suggestedBetterResponse": "Improved guest response"
}}

Important:
- Do not invent property rules that are not in the SOP.
- If the SOP says manager approval is required, do not approve the guest request.
- If the guest has an access, safety, refund, or policy-sensitive issue, consider escalation.
- If the response sounds friendly but violates the SOP, mark it as risky.
"""

#Sends the generated evaluation prompt to the OpenAI API
#Returns the LLM output
#Optional because the rule-based evaluator works without an API key
def evaluateWithLLM(guestMessage, propertyRules, aiResponse, openaiApiKey):
    client = OpenAI(api_key = openaiApiKey)
    prompt = createLLMPrompt(guestMessage, propertyRules, aiResponse)
    response = client.responses.create(
        model="gpt-4o-mini",
        input=prompt
    )
    return response.output_text

#Helper function to avoid Streamlit interpreting "$" as LaTex
def escapeMarkdown(text):
    if text is None:
        return "No text returned."
    return str(text).replace("$", "\\$")

#Parses the LLM's JSON response and displays it with the same dashboard style as the rule-based evaluator
def displayLLMResult(llmText):
    try:
        llmData = json.loads(cleanLLMJson(llmText))

        st.header(f"LLM Result: {llmData.get('decision', 'No decision returned')}")

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                label="LLM Score",
                value=f"{llmData.get('overallScore', 'N/A')} / 100"
            )

        with col2:
            decision = llmData.get("decision", "")

            if decision == "Safe to Send":
                st.success("Low risk")
            elif decision == "Review Before Sending":
                st.warning("Human review recommended")
            elif decision == "Escalate Immediately":
                st.error("Immediate escalation needed")
            else:
                st.info("LLM returned a custom decision")

        st.subheader("LLM Decision Reason")
        st.write(escapeMarkdown(llmData.get("decisionReason", "No decision reason returned.")))

        issueTypes = llmData.get("issueTypes", [])
        if issueTypes:
            st.subheader("LLM Detected Issue Types")
            st.write(", ".join(issueTypes))

        riskBreakdown = llmData.get("riskBreakdown", {})
        if riskBreakdown:
            st.subheader("LLM Risk Breakdown")
            for category, categoryScore in riskBreakdown.items():
                st.write(f"**{category}:** {categoryScore} / 100")
                st.progress(categoryScore / 100)

        flags = llmData.get("flags", [])
        if flags:
            st.subheader("LLM Flags Found")
            for flag in flags:
                st.warning(escapeMarkdown(flag))
        else:
            st.success("The LLM found no major issues.")

        upsellOpportunities = llmData.get("upsellOpportunities", [])
        if upsellOpportunities:
            st.subheader("LLM Upsell Opportunities")
            for upsell in upsellOpportunities:
                st.info(escapeMarkdown(upsell))

        st.subheader("LLM Suggested Better Response")
        llmSuggestedResponse = llmData.get("suggestedBetterResponse", "No suggested response returned.")
        st.write(escapeMarkdown(llmSuggestedResponse))

    except json.JSONDecodeError:
        st.error("The LLM returned text that was not valid JSON.")
        st.write("Raw LLM output:")
        st.code(llmText, language="text")

#Helper to remove markdown code fences from the LLM output, allowing it to be parsed as JSON
#Protects the app if the model doesn't return raw JSON
def cleanLLMJson(llmText):
    cleaned = llmText.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned.replace("```json", "", 1).strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```", "", 1).strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    return cleaned

#Display evaluation results
if st.button("Evaluate Response"):
    result = evaluateResponse(guestMessage, propertyRules, aiResponse)
    st.markdown("---")
    st.header(f"Result: {result['decision']}")
    col1, col2 = st.columns(2)

    with col1:
        st.metric(label = "Response Score", value = f"{result['score']} / 100")

    with col2:
        if result["decision"] == "Safe to Send":
            st.success("Low risk")
        elif result["decision"] == "Review Before Sending":
            st.warning("Human review recommended")
        else:
            st.error("Immediate escalation needed")

    st.subheader("Decision Reason")
    for reason in result["decisionReasons"]:
        st.write(f"- {reason}")

    if result["issueTypes"]:
        st.subheader("Detected Issue Types")
        issueText = ", ".join(result["issueTypes"])
        st.write(issueText)

    st.subheader("Risk Breakdown")
    for category, categoryScore in result["riskBreakdown"].items():
        st.write(f"**{category}:** {categoryScore} / 100")
        st.progress(categoryScore / 100)

    if result["flags"]:
        st.subheader("Flags Found")
        for flag in result["flags"]:
            st.warning(flag)
    else:
        st.success("No major issues found.")

    if result["upsells"]:
        st.subheader("Upsell Opportunities")
        for upsell in result["upsells"]:
            st.info(upsell)

    st.subheader("Suggested Better Response")
    st.write(result["suggestedResponse"])
    st.caption("This prototype evaluates AI guest responses based on common short-term rental risks: "
               "incorrect promises, missing policy details, missed upsells, and escalation-sensitive issues.")
    with st.expander("Production LLM Evaluation Prompt"):
        st.write(
            "This is the prompt that would be sent to an LLM evaluator in a hybrid production version."
        )
        st.code(createLLMPrompt(guestMessage, propertyRules, aiResponse), language="text")

    if runLLM:
        st.subheader("Optional LLM Evaluation")

        if not openaiApiKey:
            st.error("Enter an OpenAI API key in the sidebar to run the LLM evaluator.")
        else:
            try:
                with st.spinner("Running LLM evaluator..."):
                    llmResult = evaluateWithLLM(
                        guestMessage,
                        propertyRules,
                        aiResponse,
                        openaiApiKey
                    )

                displayLLMResult(llmResult)
                st.caption(
                    "The LLM evaluator is optional. The rule-based evaluator acts as a transparent guardrail layer, "
                    "while the LLM can handle more flexible language and nuanced SOP interpretation."
                )

            except Exception as e:
                st.error("The LLM evaluator failed to run.")
                st.write(e)