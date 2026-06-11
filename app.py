import sqlite3
import os
import time
import smtplib
import uuid
import json
import random
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import (
    Flask, request, redirect, render_template,
    session, abort, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from google import genai
#https://gemini.google.com/share/4aa512590bf5
# ─────────────────────────────────────────────
#  ALL 30 GEMINI PROMPTS
# ─────────────────────────────────────────────
PROMPTS = {

    # ── INNOVATOR FUNCTIONS (1–12) ──────────────────────────────────────────

    1: lambda x: f"""Extract structured startup pitch data. Return ONLY valid JSON, no markdown fences.
Pitch: {x}
Return exactly this JSON shape:
{{"problem":"","solution":"","target_market":"","market_size":"","competitive_advantage":"","team":"","funding_ask":"","product_stage":"","revenue_model":"","traction":""}}""",

    2: lambda x: f"""You are a top-tier VC partner at Sequoia. Score this startup pitch 0-100.
Pitch: {x}
Return ONLY valid JSON:
{{"total_score":85,"breakdown":{{"clarity":18,"market_opportunity":28,"innovation":22,"team_credibility":12,"feasibility":5}},"grade":"B+","summary":"One sentence summary of the pitch quality","investor_verdict":"Detailed verdict in 2 sentences"}}""",

    3: lambda x: f"""Generate a deep SWOC (Strengths, Weaknesses, Opportunities, Challenges) analysis for this startup.
Data: {x}
Return ONLY valid JSON:
{{"strengths":["specific strength 1","specific strength 2","specific strength 3"],"weaknesses":["specific weakness 1","specific weakness 2"],"opportunities":["specific opportunity 1","specific opportunity 2","specific opportunity 3"],"challenges":["specific challenge 1","specific challenge 2","specific challenge 3"],"strategic_score":72,"summary":"One-line strategic takeaway"}}""",

    4: lambda x: f"""You are a YC partner. Give 5 specific, actionable pitch improvements.
Pitch: {x}
Return ONLY valid JSON:
{{"suggestions":[{{"issue":"Market size is vague","why_it_matters":"Investors need TAM data to assess opportunity size","action":"Add: India has X million users in this segment worth Rs Y crore","priority":"High","impact_score":9}}],"overall_pitch_grade":"C+","biggest_gap":"Missing traction data"}}""",

    5: lambda x: f"""Write a crisp 200-word investor-ready executive summary. No hype, facts only.
Data: {x}
Return ONLY valid JSON:
{{"executive_summary":"Exactly 200 words professional summary here","headline":"One powerful tagline under 12 words","key_metrics":["Metric 1: value","Metric 2: value","Metric 3: value"],"investment_hook":"One sentence that makes investors want to know more"}}""",

    6: lambda x: f"""Identify ALL investor red flags in this pitch. Be harsh and specific like a skeptical VC who has seen thousands of pitches.
Pitch: {x}
Return ONLY valid JSON:
{{"risk_level":"Medium","overall_flag_count":3,"flags":[{{"type":"Financial","issue":"Claims Rs100Cr revenue in Year 2 with no current traction","severity":"High","recommendation":"Show bottom-up financial model with clear assumptions"}}],"investability_score":65,"overall_assessment":"2-sentence harsh but fair assessment"}}""",

    7: lambda x: f"""Categorize this startup precisely into the Indian startup ecosystem.
Startup: {x}
Return ONLY valid JSON:
{{"primary_category":"HealthTech","secondary_tags":["AI","Rural","B2B","Diagnostic"],"business_model":"SaaS","stage_guess":"Seed","india_relevance":"High","monetization_clarity":"Medium","sector_growth_outlook":"High growth - 40% CAGR"}}""",

    8: lambda x: f"""Identify real, named competitors in the Indian and global market with detailed analysis.
Startup: {x}
Return ONLY valid JSON:
{{"direct_competitors":[{{"name":"Company X","market_position":"Leader","differentiator":"10M users, strong brand","funding":"$50M Series B","weakness":"Poor rural penetration, high pricing","threat_level":"High"}}],"indirect_competitors":[{{"name":"Alt Solution","type":"Manual process / Excel","why_people_use_it":"Familiarity and zero cost","switching_cost":"Low"}}],"competitive_moat_score":7.5,"moat_type":"Network effect","competitive_advantage_summary":"One sentence on how this startup wins"}}""",

    9: lambda x: f"""Identify ideal investor profiles and suggest fundraising strategy for this startup.
Data: {x}
Return ONLY valid JSON:
{{"ideal_investors":[{{"type":"Seed VC","geography":"Bangalore","ticket_size":"Rs1-5 crore","example_firms":["Fireside Ventures","Blume Ventures","Stellaris"],"match_reason":"Focus on consumer tech in India","contact_approach":"LinkedIn + AngelList India"}}],"fundraising_readiness":72,"suggested_approach":"AngelList India + warm intros through IIT network","fundraising_timeline":"3-6 months","valuation_benchmark":"Rs8-15Cr pre-money at seed"}}""",

    10: lambda x: f"""Create a 12-slide investor pitch deck outline tailored to this startup.
Pitch: {x}
Return ONLY valid JSON:
{{"slides":[{{"slide_number":1,"title":"Problem","content_hint":"Show the pain point with real data and a story","design_tip":"Use before/after visual or shocking statistic","critical":true,"time_to_spend":"45 seconds"}}],"deck_score":78,"biggest_missing_slide":"Traction slide","presentation_tips":["Open with a story not a slide","End with a clear ask"]}}""",

    11: lambda x: f"""Validate financial projections like a skeptical CFO who has reviewed 500 startup models.
Data: {x}
Return ONLY valid JSON:
{{"year1_validation":{{"claimed":"Rs1Cr","verdict":"Aggressive","reasoning":"No existing traction, no distribution channel","realistic_estimate":"Rs15-25L","credibility":"Low"}},"year2_validation":{{"claimed":"Rs5Cr","verdict":"Very Aggressive","reasoning":"Assumes 5x growth without proven unit economics","realistic_estimate":"Rs1-2Cr","credibility":"Low"}},"year3_validation":{{"claimed":"Rs20Cr","verdict":"Aspirational","reasoning":"Possible only with Series A funding and strong PMF","realistic_estimate":"Rs5-8Cr","credibility":"Medium"}},"overall_credibility_score":45,"key_assumptions_missing":["Customer acquisition cost","Monthly churn rate","Sales cycle length","Headcount plan"],"recommendation":"Rebuild with bottom-up assumptions"}}""",

    12: lambda x: f"""Generate 10 tough, specific VC questions this founder will definitely face in a pitch meeting.
Pitch: {x}
Return ONLY valid JSON:
{{"questions":[{{"category":"Market","question":"Why hasn't this been solved before - what has changed in the last 2 years that makes now the right time?","difficulty":"Hard","what_to_look_for":"Founder should cite specific tech/regulatory/behavioral shifts","trap":"Founders often say no one thought of it which kills credibility"}}],"preparation_score":60,"hardest_question":"Question that will trip up most founders","recommended_prep_time":"2 weeks minimum"}}""",

    # ── INVESTOR FUNCTIONS (13–25) ──────────────────────────────────────────

    13: lambda x: f"""As a smart deal-flow AI, match investor thesis with available startups and rank the top matches.
Data: {x}
Return ONLY valid JSON:
{{"ranked_matches":[{{"pitch_id":1,"company_name":"StartupX","match_score":87,"match_reasons":["Industry aligned with thesis","Right stage - Seed","India-focused team","B2B SaaS model matches portfolio"],"mismatch_reasons":["Geography - investor prefers Bangalore, startup is Chennai-based"],"recommendation":"Strong match - schedule 30-min call this week","urgency":"High - 2 other investors already interested"}}],"filter_applied":true,"total_reviewed":50,"top_matches_count":5}}""",

    14: lambda x: f"""Calculate a precise semantic match score between this investor thesis and startup pitch.
Data: {x}
Return ONLY valid JSON:
{{"match_score":87,"match_grade":"A","match_reasons":["B2B SaaS model aligns perfectly with portfolio thesis","India-focused solves local distribution gap","Technical founding team matches preference","Problem space aligns with 2 existing portfolio companies"],"mismatch_reasons":["Early stage - investor typically prefers Series A","No existing revenue - investor prefers Rs10L+ MRR"],"recommendation":"Strong fit - pursue with initial call","conviction_level":"High","similar_portfolio_companies":["Company A - similar GTM","Company B - same sector"],"suggested_check_size":"Rs1-2 Crore for 8-12% equity"}}""",

    15: lambda x: f"""Generate a comprehensive, startup-specific due diligence checklist for this investment.
Startup: {x}
Return ONLY valid JSON:
{{"documents_to_request":["Cap table (fully diluted)","Last 12 months bank statements","MCA incorporation documents","IP assignment agreements","Customer contracts (top 3)","Technical architecture document"],"key_questions":["What is exact monthly burn and runway in months?","Walk me through unit economics - CAC, LTV, payback period","Who are your top 3 customers and what % of revenue do they represent?"],"third_party_validations":["Technical architecture audit","Reference calls with top 3 customers","Background check on co-founders","Market research validation of TAM claim"],"red_flags_to_watch":["Any litigation pending","Founder vesting cliff approaching","Single customer > 40% revenue","Undisclosed prior investors","IP owned by university or previous employer"],"estimated_dd_duration":"3-4 weeks","dd_complexity":"Medium"}}""",

    16: lambda x: f"""Conduct a deep competitive intelligence analysis including Porter's Five Forces for this investment opportunity.
Startup: {x}
Return ONLY valid JSON:
{{"direct_competitors":[{{"name":"Real Company X","market_position":"Leader","differentiator":"Strong brand recognition, 10M users","funding":"Rs500Cr Series C","weakness":"Poor rural penetration, expensive for SMEs","opportunity_for_startup":"Target underserved rural and semi-urban market"}}],"indirect_competitors":[{{"name":"Manual Process / Excel","type":"Status quo alternative","why_people_use_it":"Zero cost, familiarity","switching_barrier":"Training and change management"}}],"competitive_moat_score":7.5,"porter_analysis":{{"threat_new_entrants":{{"level":"Medium","reasoning":"Low capital barrier but network effects protect incumbents"}},"supplier_power":{{"level":"Low","reasoning":"Multiple cloud/API providers available"}},"buyer_power":{{"level":"High","reasoning":"SME customers price-sensitive with low switching cost"}},"threat_substitutes":{{"level":"Medium","reasoning":"Manual processes still dominant in Tier 2/3 cities"}},"competitive_rivalry":{{"level":"High","reasoning":"3 well-funded players, aggressive pricing wars"}}}},"strategic_recommendations":["Focus on Tier 2/3 cities where competitors have no presence","Build distribution partnerships with existing SaaS players","File patents for core AI algorithm within 6 months"]}}""",

    17: lambda x: f"""Fact-check and validate the market sizing claims (TAM/SAM/SOM) in this startup pitch.
Data: {x}
Return ONLY valid JSON:
{{"tam_validation":{{"claimed":"Rs50000Cr","actual_estimate":"Rs32000Cr","verdict":"Overstated by ~55%","reasoning":"Founder counted entire healthcare market. Actual serviceable segment is significantly smaller","methodology_used":"Bottom-up: 200M rural patients x Rs160 avg annual digital health spend","credibility_score":4}},"sam_validation":{{"claimed":"Rs10000Cr","actual_estimate":"Rs4800Cr","verdict":"Overstated by ~2x","reasoning":"Only 30% of rural areas have smartphone penetration needed for this product"}},"som_validation":{{"claimed":"Rs500Cr in Year 3","actual_estimate":"Rs80-150Cr","verdict":"Very optimistic","reasoning":"1-3% capture rate is realistic for new entrant; 5% is exceptional"}},"credibility_score":5.5,"data_sources_recommended":["IBEF Healthcare Report 2024","NASSCOM Digital Health Report","World Bank India Rural Data","Statista India Healthcare"],"recommendation":"Rebuild with bottom-up methodology and cite data sources"}}""",

    18: lambda x: f"""You are a senior VC analyst. Write a full investment committee memo for this opportunity.
Data: {x}
Return ONLY valid JSON:
{{"memo_markdown":"# INVESTMENT COMMITTEE MEMO\\n\\n**Date:** [Date]\\n**Company:** [Name]\\n**Recommendation:** INVEST\\n\\n---\\n\\n## 1. EXECUTIVE SUMMARY\\n[100-word company overview]\\n\\n**Investment Thesis:** [2 sentences on why this is a compelling bet]\\n\\n## 2. COMPANY OVERVIEW\\n**Problem:** [What problem they solve]\\n**Solution:** [Their approach]\\n**Business Model:** [How they make money]\\n**Traction:** [Current numbers]\\n\\n## 3. MARKET ANALYSIS\\n**TAM:** [Validated TAM]\\n**Growth Rate:** [CAGR]\\n\\n## 4. TEAM\\n**Founders:** [Background]\\n**Strengths:** [What makes them good]\\n**Gaps:** [What is missing]\\n\\n## 5. FINANCIALS\\n**Revenue Model:** [Details]\\n**Unit Economics:** [CAC/LTV]\\n\\n## 6. RISKS\\n| Risk | Level | Mitigation |\\n|------|-------|------------|\\n| Market timing | Medium | [How] |\\n\\n## 7. PROPOSED TERMS\\n- **Amount:** Rs X Crore\\n- **Instrument:** CCPS\\n- **Ownership:** Y%\\n\\n## 8. RECOMMENDATION\\n[Go/No-Go with clear reasoning]","recommendation":"Invest","confidence_level":72,"proposed_terms":{{"amount":"Rs2Cr","stake":"15%","instrument":"CCPS","valuation":"Rs13.3Cr post-money"}},"deal_timeline":"Close in 6-8 weeks"}}""",

    19: lambda x: f"""Analyze how this new startup fits into the investor's existing portfolio - synergies, conflicts, diversification.
Data: {x}
Return ONLY valid JSON:
{{"synergy_score":75,"synergies":["Can use Portfolio Co A distribution network to reach hospitals","Technical team can consult Portfolio Co B on AI architecture","Shared customer base with Portfolio Co C - cross-selling opportunity"],"conflicts":[{{"company":"Portfolio Co D","conflict_type":"Direct competitor","severity":"Medium","recommendation":"Get written approval from Portfolio Co D board before investing"}}],"diversification_value":"Medium - adds HealthTech exposure, reduces FinTech concentration","portfolio_concentration_before":"FinTech 45%, EdTech 30%, Other 25%","portfolio_concentration_after":"FinTech 38%, EdTech 25%, HealthTech 20%, Other 17%","follow_on_opportunity":"Series A in 18-24 months if hits Rs2Cr ARR milestone","exit_synergies":["Strategic acquisition by Portfolio Co C likely in 3-4 years","IPO candidate if market scales as projected"],"recommendation":"Strong portfolio fit - pursue with standard terms"}}""",

    20: lambda x: f"""Create a comprehensive color-coded risk assessment matrix for this investment.
Investment Data: {x}
Return ONLY valid JSON:
{{"risk_matrix":[{{"category":"Market Risk","level":"Medium","factors":["Market timing uncertainty","Slow enterprise sales cycles","Regulatory approval needed for medical claims"],"mitigation":"Require successful pilot with 5 paying enterprise clients before Series A tranche release","conditions_to_impose":["Monthly revenue reporting","Quarterly board meetings","Approval required for any pivot"]}},{{"category":"Competitive Risk","level":"High","factors":["3 well-funded incumbents","Low switching cost for customers"],"mitigation":"Ensure strong IP moat and exclusive distribution deals"}},{{"category":"Execution Risk","level":"Medium","factors":["Team lacks enterprise sales experience","Single technical co-founder"],"mitigation":"Require hiring of VP Sales within 3 months of funding"}},{{"category":"Financial Risk","level":"High","factors":["No revenue yet","12-month runway only"],"mitigation":"Milestone-based tranches: 50% now, 50% on Rs50L ARR"}},{{"category":"Regulatory Risk","level":"Low","factors":["DPDP Act compliance needed"],"mitigation":"Require data privacy audit within 60 days"}}],"overall_risk_score":6.2,"risk_summary":"Medium-risk investment with strong upside. Key risk is team lack of enterprise sales experience.","investment_conditions":["Milestone-based tranches","Board seat for investor","Monthly financials within 5th of each month","No hiring above Rs15L/year without board approval"],"recommended_stake":"15-20%","pass_conditions":["If founder refuses milestone-based tranches","If background check reveals undisclosed litigation"]}}""",

    21: lambda x: f"""Generate a detailed founder background verification and due diligence checklist.
Founder: {x}
Return ONLY valid JSON:
{{"credential_checks":[{{"item":"IIT Delhi B.Tech Degree","method":"Call IIT Delhi registrar directly","time_estimate":"2-3 business days","priority":"High"}},{{"item":"Ex-Google Engineer claim","method":"LinkedIn verification + reference from Google HR","time_estimate":"1 week","priority":"High"}}],"reputation_searches":["Google: [Name] site:linkedin.com","Google: [Name] startup India news","GitHub profile completeness and contribution history","Google Scholar for any patents or publications","Tracxn/Crunchbase for previous venture history"],"red_flag_searches":["[Name] fraud OR scam OR case OR court","MCA portal: director DIN lookup for past company failures","SEBI enforcement orders database","High Court cause list search"],"reference_check_questions":["Describe a specific time this founder faced a major setback - how did they respond?","How does this founder handle disagreement with investors or co-founders?","Would you work with or invest in this founder again? Why or why not?","What is their biggest professional weakness?","Rate their execution ability 1-10 with a specific example."],"cultural_fit_interview_questions":["What does your 10-year vision look like - not the exit, the mission?","Walk me through your most difficult co-founder conflict and how you resolved it.","If you raised Rs2Cr tomorrow, what exactly would you spend it on in Month 1?"],"estimated_verification_time":"7-10 business days"}}""",

    22: lambda x: f"""Recommend detailed term sheet parameters based on startup stage, traction, and Indian market norms.
Data: {x}
Return ONLY valid JSON:
{{"pre_money_valuation":"Rs13.3Cr","methodology":"Revenue multiple: 5x ARR plus 2x user traction premium","valuation_range":{{"low":"Rs10Cr","high":"Rs18Cr","recommended":"Rs13.3Cr"}},"investment_amount":"Rs2Cr","instrument":"CCPS (Compulsorily Convertible Preference Shares)","equity_stake":"15%","liquidation_preference":"1x non-participating - standard for seed","anti_dilution":"Weighted average broad-based - investor-friendly but founder-fair","board_seats":{{"investor":1,"founder":2,"independent":1,"notes":"Independent director to be mutually agreed within 90 days"}},"vesting":{{"founders_schedule":"4-year with 1-year cliff (25% vest at month 12, then monthly)","acceleration":"Single trigger: 100% vest on acquisition at less than 3x return","esop_pool":"10% to be created pre-investment"}},"information_rights":["Monthly P&L and MIS within 5th of each month","Quarterly board meeting (minimum)","Annual audited financials within 90 days of FY end","Immediate notification of material adverse events"],"protective_provisions":["Approval for new funding round more than Rs1Cr","Approval for M&A, asset sale, or IP licensing","Annual budget approval and changes more than 20%","Key employee hiring more than Rs20L CTC","Any related-party transactions"],"exit_provisions":["Drag-along after Year 5 if no liquidity event","Tag-along on any secondary sale more than 5% stake","Right of First Refusal on founder share transfers","Co-sale right on founder secondary transactions"],"standard_conditions":["Satisfactory legal due diligence","No material adverse change","Founder employment agreements executed","IP fully assigned to company"]}}""",

    23: lambda x: f"""Generate 4 professionally written investor-to-founder emails for different scenarios.
Context: {x}
Return ONLY valid JSON:
{{"emails":[{{"type":"Expression of Interest","subject":"Re: [Company Name] - Very interested in connecting","body":"Dear [Founder Name],\\n\\nThank you for sharing the [Company Name] pitch deck. I have gone through it carefully and wanted to reach out personally.\\n\\nWhat stood out to me:\\n- [Specific aspect 1 - be genuine]\\n- [Specific aspect 2 - market insight]\\n- [Specific aspect 3 - team strength]\\n\\nI believe this aligns strongly with our thesis around [relevant thesis point]. I would love to schedule a 30-minute call to learn more about your traction and roadmap. Are you available [Day] or [Day] this week?\\n\\nWarm regards,\\n[Investor Name]\\n[Fund Name]","tone":"Warm and specific","send_within":"24 hours of reviewing deck"}},{{"type":"Polite Pass","subject":"Re: [Company Name] pitch - Following up","body":"Dear [Founder Name],\\n\\nThank you for taking the time to walk me through [Company Name]. I have given this careful consideration.\\n\\nUnfortunately we will not be moving forward at this stage. To be specific:\\n\\n[Honest specific reason - e.g. We already have a portfolio company in the diagnostic AI space and cannot create a conflict OR At this stage we require Rs10L+ MRR before making a seed investment and we would love to reconnect once you hit that milestone.]\\n\\nThis is not a reflection on the quality of your idea. I think [specific genuine compliment]. The timing simply does not work for our fund right now.\\n\\nI would genuinely encourage you to reach out to [Specific VC firm] - they have backed similar companies.\\n\\nWishing you the very best,\\n[Investor Name]","tone":"Honest and helpful - not generic"}},{{"type":"Request More Information","subject":"[Company Name] - A few follow-up questions before we proceed","body":"Dear [Founder Name],\\n\\nI have reviewed the deck and I am genuinely interested.\\n\\nBefore we schedule a deeper conversation could you share:\\n\\n1. Detailed financial model - Last 6 months actuals plus 24-month projections\\n2. Cap table - Current ownership and any convertible notes outstanding\\n3. Customer evidence - 2-3 reference customer names\\n4. Technical overview - 1-pager on your AI/ML architecture\\n5. Team backgrounds - LinkedIn profiles of all co-founders\\n\\nCould you share these by [Date]? Once reviewed I will get back to you within 3 business days.\\n\\nLooking forward,\\n[Investor Name]","tone":"Professional and specific"}},{{"type":"Meeting Invitation","subject":"[Company Name] - Let us connect: [Date options]","body":"Dear [Founder Name],\\n\\nI would love to schedule a 60-minute meeting to discuss [Company Name] in depth.\\n\\nProposed times (IST):\\n- [Day Date] at 10:00 AM\\n- [Day Date] at 2:00 PM\\n- [Day Date] at 11:00 AM\\n\\nMeeting agenda:\\n1. (5 min) Quick intros\\n2. (20 min) Founder presentation - product demo preferred\\n3. (25 min) Q and A\\n4. (10 min) Discussion of terms and timeline\\n\\nPlease prepare:\\n- Live product demo if possible\\n- Latest financial model\\n- Key traction metrics on one slide\\n\\nLooking forward to it,\\n[Investor Name]","tone":"Enthusiastic and organized"}}]}}""",

    24: lambda x: f"""Prepare a complete 60-minute investor-founder meeting playbook with questions and red flags.
Startup: {x}
Return ONLY valid JSON:
{{"meeting_type":"First due diligence meeting","agenda":[{{"time":"00:00 - 05:00","activity":"Introductions and rapport building","investor_notes":"Ask about founder background informally. Notice how they describe their journey - passion vs opportunism","target":"Make founder comfortable to be candid"}},{{"time":"05:00 - 25:00","activity":"Founder presentation and product demo","investor_notes":"Pay attention to what they choose NOT to mention. Watch for rehearsed vs genuine answers. Ask for live demo.","target":"Understand product depth and founder conviction"}},{{"time":"25:00 - 50:00","activity":"Deep Q and A","investor_notes":"Use the question list below. Save hardest questions for 35-minute mark when defenses are lower.","target":"Validate assumptions and spot red flags"}},{{"time":"50:00 - 58:00","activity":"Terms and next steps discussion","investor_notes":"Only enter this if you have 70%+ conviction. Do not anchor on valuation first - let founder speak.","target":"Gauge founder expectations on terms"}},{{"time":"58:00 - 60:00","activity":"Wrap-up","investor_notes":"Always end on a positive note regardless of decision. Commit to a follow-up timeline.","target":"Leave door open for future even if passing"}}],"key_questions":[{{"category":"Product","question":"Walk me through your technical architecture - specifically what is the hardest technical problem you have solved?","difficulty":"Medium","red_flag_if":"Founders give a vague marketing answer instead of technical depth","follow_up":"Who on your team built this? What would it take for a competitor to replicate it in 6 months?"}},{{"category":"Market","question":"Who said no to you - which customers tried your product and churned and why?","difficulty":"Hard","red_flag_if":"Founder says we have no churn or deflects","follow_up":"What did you learn from that and how did you change the product?"}},{{"category":"Financials","question":"Tell me your exact monthly burn right now and your runway in months without any new funding.","difficulty":"Hard","red_flag_if":"Founder does not know the number off the top of their head","follow_up":"What happens to the business if you do not close this round?"}},{{"category":"Team","question":"Describe the worst disagreement you have had with your co-founder - what was it about and how was it resolved?","difficulty":"Hard","red_flag_if":"Says they have never had a serious disagreement - means either dishonest or have not been tested","follow_up":"What is one thing your co-founder does better than you?"}},{{"category":"Competition","question":"Tell me about the best-funded competitor and why a customer would choose them over you tomorrow.","difficulty":"Medium","red_flag_if":"Dismisses competition or says we have no direct competitors","follow_up":"If they raised another Rs100Cr tomorrow what would you do differently?"}}],"red_flags_to_watch":["Defensive or evasive when asked about burn rate or financials","Dismisses all competition as inferior without specific evidence","Cannot give a clear answer on who their best 3 customers are","Founders contradict each other on key facts","Overpromises on timeline - 6 months to profitability type claims","Talks more about the exit than the mission","Cannot explain their AI or tech in plain English"],"documents_to_request_after_meeting":["Fully diluted cap table","Last 6 months bank statements","Two reference customer contacts (we call them directly)","Technical architecture one-pager","MCA filings and incorporation documents"],"post_meeting_actions":["Send thank-you email within 2 hours","Write investment memo draft within 24 hours","Call 2 references within 48 hours","Decision email within 5 business days - never leave founders hanging"]}}""",

    25: lambda x: f"""Model 3 detailed ROI exit scenarios with full financial calculations and IRR.
Investment: {x}
Return ONLY valid JSON:
{{"investment_details":{{"amount":"Rs2Cr","stake":"15%","post_money_valuation":"Rs13.3Cr","entry_date":"2024","instrument":"CCPS"}},"scenarios":{{"base_case":{{"probability":"60%","description":"Steady growth, achieves Series A in 18 months","arr_year1":"Rs1.2Cr","arr_year3":"Rs8Cr","arr_year5":"Rs24Cr","arr_cagr":"3x YoY","exit_year":5,"exit_multiple":"8x ARR (SaaS industry standard)","exit_valuation":"Rs192Cr","dilution_to_year5":"30% (Series A + B)","effective_stake_at_exit":"10.5%","investor_proceeds":"Rs20.2Cr","roi":"10.1x","irr":"59%","moic":"10.1x"}},"bull_case":{{"probability":"25%","description":"Exceptional growth, becomes category leader","arr_year5":"Rs60Cr","arr_cagr":"4x YoY","exit_year":4,"exit_multiple":"15x ARR (premium SaaS)","exit_valuation":"Rs900Cr","dilution_to_exit":"20%","effective_stake_at_exit":"12%","investor_proceeds":"Rs108Cr","roi":"54x","irr":"153%","moic":"54x"}},"bear_case":{{"probability":"15%","description":"Struggles with growth, acqui-hire or low exit","arr_year5":"Rs4Cr","arr_cagr":"1.5x YoY","exit_year":6,"exit_multiple":"3x ARR (distressed)","exit_valuation":"Rs12Cr","dilution_to_exit":"35%","effective_stake_at_exit":"9.75%","investor_proceeds":"Rs1.17Cr","roi":"0.59x","irr":"-8%","moic":"0.59x"}}}},"weighted_expected_value":"Rs25.4Cr","weighted_irr":"72%","weighted_moic":"12.7x","dilution_notes":"Assumes Series A (20% dilution) and no further rounds in base case","fees_and_carry":"2% management fee reduces proceeds; 20% carry reduces net IRR by ~8%","benchmark":"Top-quartile seed fund targets 3x MOIC; this investment targets 12x","summary":"Highly attractive risk-reward profile. Even in bear case company survives. Bull case is a fund-returner."}}""",

    # ── ADMIN FUNCTIONS (26–30) ──────────────────────────────────────────────

    26: lambda x: f"""Detect spam or fraud in this startup pitch with high precision. Be thorough.
Pitch: {x}
Return ONLY valid JSON:
{{"is_spam":false,"is_scam":false,"confidence":97,"spam_score":3,"fraud_indicators":[],"violations":[],"mlm_language_detected":false,"get_rich_quick_language":false,"fabricated_metrics_risk":"Low","plagiarism_risk":"Low","action_required":"None","recommendation":"Approve for review","flagged_phrases":[],"overall_assessment":"Legitimate startup pitch with authentic business model"}}""",

    27: lambda x: f"""Moderate this pitch content for policy violations. Check all categories thoroughly.
Text: {x}
Return ONLY valid JSON:
{{"is_safe":true,"overall_safety_score":96,"violations":[],"hate_speech_check":{{"result":"Clean","details":"No discriminatory language detected"}},"illegal_activities_check":{{"result":"Clean","details":"No illegal business model or activity"}},"misinformation_check":{{"result":"Clean","details":"No obviously fabricated claims"}},"inappropriate_content_check":{{"result":"Clean","details":"Professional tone throughout"}},"profanity_check":{{"result":"Clean","details":"No profanity"}},"plagiarism_risk":"Low","action_required":"None","confidence":96,"reviewer_notes":"Standard startup pitch, ready for investor review"}}""",

    28: lambda x: f"""Detect if this is a duplicate or near-duplicate pitch submission. Compare carefully.
Pitches: {x}
Return ONLY valid JSON:
{{"is_duplicate":false,"confidence":12,"similarity_score":8,"same_founder":false,"same_product":false,"same_company_name":false,"text_similarity_percent":8,"reasoning":"Different companies, founders, and business models. Similarity is only in generic pitch language used by most startups.","differences":["Different problem statements","Different target markets","Different founding teams","Different revenue models"],"action":"Allow - unique and original submission","merge_recommended":false}}""",

    29: lambda x: f"""Evaluate pitch quality against platform standards and decide auto-approve or reject.
Data: {x}
Return ONLY valid JSON:
{{"approved":true,"completeness_score":82,"professionalism_score":78,"substantiveness_score":80,"overall_score":80,"completeness_details":{{"problem":true,"solution":true,"market":true,"team":true,"financials":false}},"professionalism_details":{{"grammar":"Good","structure":"Logical","tone":"Professional","clarity":"High"}},"substantiveness_details":{{"specific_customer":true,"realistic_financials":false,"clear_differentiation":true}},"reason":"Meets platform quality standards. Missing detailed financial projections but core pitch is strong.","required_improvements":["Add specific financial projections for Year 1-3","Include founder LinkedIn profiles or brief bios"],"auto_approved":true,"reviewer_flag":false,"quality_tier":"Tier 2 - Good"}}""",

    30: lambda x: f"""Analyze platform-wide startup trend data and generate actionable insights for the admin team.
Stats: {x}
Return ONLY valid JSON:
{{"top_industries":[{{"name":"AI/ML","count":23,"growth":"+35% MoM","avg_score":74}},{{"name":"HealthTech","count":18,"growth":"+28% MoM","avg_score":71}},{{"name":"FinTech","count":15,"growth":"-5% MoM","avg_score":68}}],"geographic_insights":{{"top_cities":["Bangalore (32%)","Mumbai (24%)","Delhi (18%)","Chennai (12%)","Hyderabad (8%)"],"tier2_growth":"+41% QoQ","emerging_cities":["Pune","Coimbatore","Jaipur"]}},"funding_insights":{{"avg_ask":"Rs3.4Cr","median_ask":"Rs2Cr","trend":"Valuations up 14% MoM","most_common_stage":"Seed (68% of submissions)"}},"quality_trends":{{"avg_score":69,"improving":true,"improvement_rate":"+3.2 points MoM","lowest_scoring_category":"Financial projections (avg 42/100)"}},"hot_sectors":["HealthTech","CleanTech","AgriTech 2.0","D2C Brands"],"underserved_sectors":["AgriTech (high quality pitches, low investor interest)","Rural EdTech","Waste Management Tech"],"investor_demand_gaps":["Need 5 more HealthTech-focused seed investors","Need impact investors for CleanTech","Need Tier 2 city-focused VCs"],"predictions":["HealthTech submissions will grow 40% next month based on trend","CleanTech will emerge as top 3 category within 60 days"],"platform_recommendations":["Actively recruit 10 HealthTech seed investors this month","Launch Hindi-language pitch submission to unlock Tier 2 founders","Create CleanTech-focused investor matching campaign","Add financial projection template to reduce common gaps"],"monthly_report_summary":"Platform showing strong growth. Quality improving. HealthTech is the breakout category. Recommend recruiting more sector-specific investors."}}"""
}

# ─────────────────────────────────────────────
#  APP SETUP
# ─────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dreamlaunch-secret-2025")

DB          = "dreamlaunch.db"
MODEL       = "gemini-2.5-flash"
RATE_LIMIT  = 60
WINDOW      = 60

client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY", "GEMINI_API_KEY")
)

rate_store = {}

app.config.update({
    "SMTP_SERVER":   "smtp.gmail.com",
    "SMTP_PORT":     587,
    "SMTP_USERNAME": os.environ.get("SMTP_USER", "DreamlaunchServerSystemService@gmail.com"),
    "SMTP_PASSWORD": os.environ.get("SMTP_PASS", "spziwjdeksnzumwi"),
})

# ─────────────────────────────────────────────
#  FUNCTION METADATA  (icon, name, role, desc)
# ─────────────────────────────────────────────
FN_META = {
    1:  {"name": "Pitch Extraction",      "role": "innovator", "icon": "🔍",
         "desc": "Structures raw pitch into clean data"},
    2:  {"name": "Quality Score",         "role": "innovator", "icon": "⭐",
         "desc": "Scores pitch 0-100 like a VC partner"},
    3:  {"name": "SWOC Analysis",         "role": "innovator", "icon": "📊",
         "desc": "Strengths, Weaknesses, Opportunities, Challenges"},
    4:  {"name": "Improvement Tips",      "role": "innovator", "icon": "💡",
         "desc": "5 actionable pitch improvements from a YC partner"},
    5:  {"name": "Executive Summary",     "role": "innovator", "icon": "📝",
         "desc": "200-word investor-ready executive summary"},
    6:  {"name": "Red Flag Detection",    "role": "innovator", "icon": "🚩",
         "desc": "Spots investor concerns and risks"},
    7:  {"name": "Industry Tagging",      "role": "innovator", "icon": "🏷️",
         "desc": "Auto-categorises into startup ecosystem"},
    8:  {"name": "Competitor Mapping",    "role": "innovator", "icon": "🗺️",
         "desc": "Real named competitors with their weaknesses"},
    9:  {"name": "Investor Profiling",    "role": "innovator", "icon": "🎯",
         "desc": "Ideal investor types and fundraising strategy"},
    10: {"name": "Deck Outline",          "role": "innovator", "icon": "🎴",
         "desc": "12-slide investor deck structure"},
    11: {"name": "Financial Validation",  "role": "innovator", "icon": "💰",
         "desc": "CFO-level financial projection audit"},
    12: {"name": "VC Question Prep",      "role": "innovator", "icon": "❓",
         "desc": "10 tough questions you will face in meetings"},
    13: {"name": "Smart Filtering",       "role": "investor",  "icon": "🔬",
         "desc": "Ranks pitches by thesis alignment"},
    14: {"name": "Semantic Match Score",  "role": "investor",  "icon": "🎯",
         "desc": "% match between your thesis and a startup"},
    15: {"name": "DD Checklist",          "role": "investor",  "icon": "✅",
         "desc": "Full due diligence checklist per startup"},
    16: {"name": "Competitive Intel",     "role": "investor",  "icon": "🕵️",
         "desc": "Porter's Five Forces & competitor analysis"},
    17: {"name": "Market Size Validator", "role": "investor",  "icon": "📐",
         "desc": "Fact-checks TAM/SAM/SOM claims"},
    18: {"name": "Investment Memo",       "role": "investor",  "icon": "📄",
         "desc": "Full investment committee memo (2000 words)"},
    19: {"name": "Portfolio Fit",         "role": "investor",  "icon": "🧩",
         "desc": "Synergies and conflict with your portfolio"},
    20: {"name": "Risk Assessment",       "role": "investor",  "icon": "⚠️",
         "desc": "Color-coded risk matrix with mitigations"},
    21: {"name": "Founder Background",    "role": "investor",  "icon": "🔎",
         "desc": "Verification checklist for founders"},
    22: {"name": "Term Sheet Rec.",       "role": "investor",  "icon": "📋",
         "desc": "Recommended term sheet parameters"},
    23: {"name": "Email Generator",       "role": "investor",  "icon": "📧",
         "desc": "4 professional investor-to-founder emails"},
    24: {"name": "Meeting Playbook",      "role": "investor",  "icon": "🤝",
         "desc": "60-min meeting agenda and tough questions"},
    25: {"name": "ROI Projections",       "role": "investor",  "icon": "📈",
         "desc": "3-scenario exit model with IRR and MOIC"},
    26: {"name": "Spam Detection",        "role": "admin",     "icon": "🛡️",
         "desc": "Detects fraud and spam in pitches"},
    27: {"name": "Content Moderation",    "role": "admin",     "icon": "🔒",
         "desc": "Checks for policy violations"},
    28: {"name": "Duplicate Detection",   "role": "admin",     "icon": "🔁",
         "desc": "Finds resubmitted or plagiarised pitches"},
    29: {"name": "Quality Gate",          "role": "admin",     "icon": "🏆",
         "desc": "Auto-approve or reject by quality score"},
    30: {"name": "Trend Analysis",        "role": "admin",     "icon": "📉",
         "desc": "Platform-wide startup ecosystem insights"},
}

# ─────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────
def db():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    con = db()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT,
            email       TEXT UNIQUE,
            password    TEXT,
            role        TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS pitches (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            title       TEXT DEFAULT '',
            raw_text    TEXT,
            analysis    TEXT DEFAULT '{}',
            score       INTEGER DEFAULT 0,
            category    TEXT DEFAULT 'Processing',
            status      TEXT DEFAULT 'ACTIVE',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS function_history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER,
            pitch_id      INTEGER DEFAULT 0,
            function_num  INTEGER,
            function_name TEXT,
            result_json   TEXT,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            pitch_id    INTEGER,
            sender_id   INTEGER,
            receiver_id INTEGER,
            message     TEXT,
            is_read     INTEGER DEFAULT 0,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS payments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            investor_id INTEGER,
            pitch_id    INTEGER,
            order_id    TEXT,
            amount      INTEGER,
            status      TEXT DEFAULT 'PENDING'
        );
        CREATE TABLE IF NOT EXISTS investor_profiles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER UNIQUE,
            thesis      TEXT DEFAULT '',
            industries  TEXT DEFAULT '',
            stage       TEXT DEFAULT 'Seed',
            ticket_min  INTEGER DEFAULT 0,
            ticket_max  INTEGER DEFAULT 0,
            geography   TEXT DEFAULT '',
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            title       TEXT,
            body        TEXT,
            type        TEXT DEFAULT 'info',
            is_read     INTEGER DEFAULT 0,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Seed admin — password: Admin@123
    con.execute(
        "INSERT OR IGNORE INTO users (id,name,email,password,role) VALUES (?,?,?,?,?)",
        (1, "Admin", "admin@dreamlaunch.in",
         generate_password_hash("Admin@123"), "admin")
    )
    con.commit()
    con.close()

init_db()

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def rate_limit_check(ip):
    now = time.time()
    w   = [t for t in rate_store.get(ip, []) if now - t < WINDOW]
    if len(w) >= RATE_LIMIT:
        abort(429)
    w.append(now)
    rate_store[ip] = w

def gemini_call(prompt):
    r = client.models.generate_content(model=MODEL, contents=prompt)
    return r.text

def safe_json_parse(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text  = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        return {"raw": text, "parse_error": True}

def send_email(to_email, subject, plain_body):
    try:
        msg = MIMEMultipart("alternative")
        msg["From"]    = app.config["SMTP_USERNAME"]
        msg["To"]      = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(plain_body, "plain"))
        with smtplib.SMTP(app.config["SMTP_SERVER"], app.config["SMTP_PORT"]) as s:
            s.starttls()
            s.login(app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"])
            s.sendmail(app.config["SMTP_USERNAME"], to_email, msg.as_string())
    except Exception as e:
        print(f"Email error: {e}")

def send_email_html(to_email, subject, html_body):
    try:
        msg = MIMEMultipart("alternative")
        msg["From"]    = app.config["SMTP_USERNAME"]
        msg["To"]      = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(app.config["SMTP_SERVER"], app.config["SMTP_PORT"]) as s:
            s.starttls()
            s.login(app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"])
            s.sendmail(app.config["SMTP_USERNAME"], to_email, msg.as_string())
    except Exception as e:
        print(f"Email HTML error: {e}")

def save_fn_history(user_id, pitch_id, fn_num, result_dict):
    meta = FN_META.get(fn_num, {})
    con  = db()
    con.execute(
        "INSERT INTO function_history (user_id,pitch_id,function_num,function_name,result_json) VALUES (?,?,?,?,?)",
        (user_id, pitch_id or 0, fn_num,
         meta.get("name", f"Function {fn_num}"),
         json.dumps(result_dict))
    )
    con.commit()
    con.close()

def get_fn_history(user_id, pitch_id=None):
    con = db()
    if pitch_id:
        rows = con.execute(
            "SELECT * FROM function_history WHERE user_id=? AND pitch_id=? ORDER BY id DESC LIMIT 60",
            (user_id, pitch_id)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT * FROM function_history WHERE user_id=? ORDER BY id DESC LIMIT 60",
            (user_id,)
        ).fetchall()
    con.close()
    return [dict(r) for r in rows]

def add_notification(user_id, title, body, ntype="info"):
    con = db()
    con.execute(
        "INSERT INTO notifications (user_id,title,body,type) VALUES (?,?,?,?)",
        (user_id, title, body, ntype)
    )
    con.commit()
    con.close()

def get_notifications(user_id):
    con  = db()
    rows = con.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (user_id,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.before_request
def guard():
    rate_limit_check(request.remote_addr)

# ─────────────────────────────────────────────
#  ROUTES: PUBLIC
# ─────────────────────────────────────────────
@app.route("/")
def landing():
    return render_template("landing.html")

# ─────────────────────────────────────────────
#  ROUTES: AUTH
# ─────────────────────────────────────────────
@app.route("/register/<role>", methods=["GET", "POST"])
def register(role):
    if role not in ("innovator", "investor"):
        abort(404)
    if request.method == "POST":
        name  = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        pwd   = request.form.get("password", "")
        if not all([name, email, pwd]):
            return render_template("auth.html", role=role, mode="register",
                                   error="All fields are required.")
        con = db()
        try:
            con.execute(
                "INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)",
                (name, email, generate_password_hash(pwd), role)
            )
            con.commit()
        except sqlite3.IntegrityError:
            con.close()
            return render_template("auth.html", role=role, mode="register",
                                   error="Email already registered.")
        con.close()
        return redirect(f"/login/{role}")
    return render_template("auth.html", role=role, mode="register")

@app.route("/login/innovator", methods=["GET", "POST"])
def login_innovator():
    if request.method == "POST":
        con = db()
        u   = con.execute(
            "SELECT * FROM users WHERE email=? AND role='innovator'",
            (request.form.get("email", ""),)
        ).fetchone()
        con.close()
        if not u or not check_password_hash(u["password"], request.form.get("password", "")):
            return render_template("auth.html", role="innovator", mode="login",
                                   error="Invalid email or password.")
        session.update({"uid": u["id"], "role": "innovator", "name": u["name"]})
        return redirect("/innovator")
    return render_template("auth.html", role="innovator", mode="login")

@app.route("/login/investor", methods=["GET", "POST"])
def login_investor():
    if request.method == "POST":
        con = db()
        u   = con.execute(
            "SELECT * FROM users WHERE email=? AND role='investor'",
            (request.form.get("email", ""),)
        ).fetchone()
        con.close()
        if not u or not check_password_hash(u["password"], request.form.get("password", "")):
            return render_template("auth.html", role="investor", mode="login",
                                   error="Invalid email or password.")
        otp = str(random.randint(100000, 999999))
        session.update({
            "otp": otp, "otp_time": time.time(),
            "otp_attempts": 0, "otp_lock_until": None,
            "tmp_user": u["id"], "tmp_name": u["name"],
            "tmp_role": "investor", "otp_email": request.form["email"]
        })
        send_email(
            request.form["email"],
            "DreamLaunch — Your Login OTP",
            f"Your DreamLaunch OTP is: {otp}\nValid for 10 minutes.\nDo not share this with anyone."
        )
        return render_template("auth.html", role="investor", mode="otp",
                               email=request.form["email"])
    return render_template("auth.html", role="investor", mode="login")

@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    now  = time.time()
    lock = session.get("otp_lock_until")
    if lock and now < lock:
        return render_template("auth.html", role="investor", mode="otp",
                               error=f"Too many attempts. Wait {int(lock - now)}s.",
                               email=session.get("otp_email"))
    if request.form.get("otp") == session.get("otp"):
        if now - session.get("otp_time", 0) > 600:
            return render_template("auth.html", role="investor", mode="otp",
                                   error="OTP expired. Please login again.",
                                   email=session.get("otp_email"))
        session["uid"]  = session.pop("tmp_user")
        session["role"] = session.pop("tmp_role")
        session["name"] = session.pop("tmp_name", "Investor")
        for k in ["otp", "otp_time", "otp_attempts", "otp_lock_until", "otp_email"]:
            session.pop(k, None)
        return redirect("/investor")
    session["otp_attempts"] = session.get("otp_attempts", 0) + 1
    if session["otp_attempts"] >= 3:
        session["otp_lock_until"] = now + 60
        session["otp_attempts"]   = 0
        return render_template("auth.html", role="investor", mode="otp",
                               error="Too many attempts. Locked for 60 seconds.",
                               email=session.get("otp_email"))
    left = 3 - session["otp_attempts"]
    return render_template("auth.html", role="investor", mode="otp",
                           error=f"Invalid OTP. {left} attempt(s) left.",
                           email=session.get("otp_email"))

@app.route("/login/admin", methods=["GET", "POST"])
def login_admin():
    if request.method == "POST":
        email = request.form.get("email", "")
        pwd   = request.form.get("password", "")
        con   = db()
        u     = con.execute(
            "SELECT * FROM users WHERE email=? AND role='admin'", (email,)
        ).fetchone()
        con.close()
        if not u or not check_password_hash(u["password"], pwd):
            return render_template("auth.html", role="admin", mode="login",
                                   error="Invalid credentials.")
        session.update({"uid": u["id"], "role": "admin", "name": u["name"]})
        return redirect("/admin")
    return render_template("auth.html", role="admin", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/dashboard")
def dashboard():
    r = session.get("role")
    if r == "innovator": return redirect("/innovator")
    if r == "investor":  return redirect("/investor")
    if r == "admin":     return redirect("/admin")
    abort(403)

# ─────────────────────────────────────────────
#  ROUTES: INNOVATOR
# ─────────────────────────────────────────────
@app.route("/innovator", methods=["GET", "POST"])
def innovator():
    if session.get("role") != "innovator":
        abort(403)
    con = db()
    uid = session["uid"]

    if request.method == "POST":
        raw_pitch = request.form.get("pitch", "").strip()
        title     = request.form.get("title", "").strip() or raw_pitch[:60]
        if not raw_pitch:
            con.close()
            return redirect("/innovator")

        cursor   = con.execute(
            "INSERT INTO pitches (user_id,title,raw_text,analysis,score,category,status) VALUES (?,?,?,?,?,?,?)",
            (uid, title, raw_pitch, json.dumps({}), 0, "Processing...", "ACTIVE")
        )
        pitch_id = cursor.lastrowid
        con.commit()

        analysis_acc    = {}
        score, category = 0, "General"

        # Run Innovator nodes 1-12 + quality gates 26, 29
        for i in list(range(1, 13)) + [26, 29]:
            try:
                resp   = client.models.generate_content(model=MODEL, contents=PROMPTS[i](raw_pitch))
                parsed = safe_json_parse(resp.text)
                analysis_acc[f"node_{i}"] = parsed

                if i == 2 and isinstance(parsed, dict):
                    score = int(parsed.get("total_score", 0))
                if i == 7 and isinstance(parsed, dict):
                    cat = parsed.get("primary_category", "")
                    if cat:
                        category = cat

                con.execute(
                    "UPDATE pitches SET analysis=?,score=?,category=? WHERE id=?",
                    (json.dumps(analysis_acc), score, category, pitch_id)
                )
                con.commit()
                save_fn_history(uid, pitch_id, i, parsed)
            except Exception as e:
                analysis_acc[f"node_{i}"] = {"error": str(e)}
                con.execute("UPDATE pitches SET analysis=? WHERE id=?",
                            (json.dumps(analysis_acc), pitch_id))
                con.commit()

        add_notification(uid, "Pitch Analysed! 🎉",
                         f"Your pitch '{title}' scored {score}/100.", "success")
        con.close()
        return redirect("/innovator")

    # GET
    rows    = con.execute(
        "SELECT * FROM pitches WHERE user_id=? ORDER BY id DESC", (uid,)
    ).fetchall()
    pitches = [dict(r) for r in rows]
    history = get_fn_history(uid)
    notifs  = get_notifications(uid)
    con.close()

    return render_template(
        "innovator_dashboard.html",
        pitches_json=json.dumps(pitches),
        history_json=json.dumps(history),
        notifs_json=json.dumps(notifs),
        fn_meta=json.dumps(FN_META),
        user_name=session.get("name", "Founder"),
        user_id=uid,
    )

# ─────────────────────────────────────────────
#  API: fetch single pitch (innovator)
# ─────────────────────────────────────────────
@app.route("/api/pitch/<int:pid>")
def api_pitch(pid):
    if "uid" not in session:
        abort(403)
    con = db()
    row = con.execute(
        "SELECT * FROM pitches WHERE id=? AND user_id=?",
        (pid, session["uid"])
    ).fetchone()
    con.close()
    if not row:
        abort(404)
    return jsonify(dict(row))

# ─────────────────────────────────────────────
#  API: run any node on innovator-owned pitch
# ─────────────────────────────────────────────
@app.route("/api/run_node/<int:pid>/<int:node>", methods=["POST"])
def run_extra_node(pid, node):
    if session.get("role") != "innovator":
        abort(403)
    if node not in range(1, 31):
        abort(400)
    uid = session["uid"]
    con = db()
    row = con.execute(
        "SELECT * FROM pitches WHERE id=? AND user_id=?", (pid, uid)
    ).fetchone()
    if not row:
        con.close()
        abort(404)

    body    = request.get_json(silent=True) or {}
    context = row["raw_text"]
    if node == 14:
        thesis  = body.get("thesis", "General VC investing in Indian startups")
        context = f"Investor Thesis: {thesis}\nStartup Pitch: {context}"
    elif node == 25:
        amount  = body.get("amount", "Rs2 crore")
        stake   = body.get("stake", "15%")
        context = f"Investment Amount: {amount}, Stake: {stake}, Startup: {context}"

    try:
        resp     = client.models.generate_content(model=MODEL, contents=PROMPTS[node](context))
        parsed   = safe_json_parse(resp.text)
        analysis = json.loads(row["analysis"] or "{}")
        analysis[f"node_{node}"] = parsed
        con.execute("UPDATE pitches SET analysis=? WHERE id=?",
                    (json.dumps(analysis), pid))
        con.commit()
        con.close()
        save_fn_history(uid, pid, node, parsed)
        return jsonify({"success": True, "data": parsed, "node": node})
    except Exception as e:
        con.close()
        return jsonify({"success": False, "error": str(e)}), 500

# ─────────────────────────────────────────────
#  API: function history
# ─────────────────────────────────────────────
@app.route("/api/history")
def api_history_all():
    if "uid" not in session:
        abort(403)
    return jsonify(get_fn_history(session["uid"]))

@app.route("/api/history/<int:pid>")
def api_history_pitch(pid):
    if "uid" not in session:
        abort(403)
    return jsonify(get_fn_history(session["uid"], pitch_id=pid))

# ─────────────────────────────────────────────
#  API: notifications
# ─────────────────────────────────────────────
@app.route("/api/notifications")
def api_notifications():
    if "uid" not in session:
        abort(403)
    return jsonify(get_notifications(session["uid"]))

@app.route("/api/notifications/read_all", methods=["POST"])
def mark_notifs_read():
    if "uid" not in session:
        abort(403)
    con = db()
    con.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (session["uid"],))
    con.commit()
    con.close()
    return jsonify({"ok": True})

# ─────────────────────────────────────────────
#  ROUTES: INVESTOR
# ─────────────────────────────────────────────
@app.route("/investor")
def investor():
    if session.get("role") != "investor":
        abort(403)
    uid = session["uid"]
    con = db()

    rows      = con.execute(
        "SELECT * FROM pitches WHERE status='ACTIVE' ORDER BY score DESC"
    ).fetchall()
    paid_pids = [p["pitch_id"] for p in con.execute(
        "SELECT pitch_id FROM payments WHERE investor_id=? AND status='SUCCESS'", (uid,)
    ).fetchall()]

    profile      = con.execute(
        "SELECT * FROM investor_profiles WHERE user_id=?", (uid,)
    ).fetchone()
    profile_dict = dict(profile) if profile else {}

    pitches_list = []
    for r in rows:
        analysis = json.loads(r["analysis"] or "{}")
        n1 = analysis.get("node_1", {})
        n2 = analysis.get("node_2", {})
        n3 = analysis.get("node_3", {})
        n7 = analysis.get("node_7", {})
        n8 = analysis.get("node_8", {})
        pitches_list.append({
            "id":               r["id"],
            "title":            r["title"] or r["raw_text"][:60] + "...",
            "raw_text":         r["raw_text"],
            "score":            r["score"] or 0,
            "category":         r["category"] or "General",
            "grade":            n2.get("grade", "N/A")              if isinstance(n2, dict) else "N/A",
            "tags":             n7.get("secondary_tags", [])        if isinstance(n7, dict) else [],
            "business_model":   n7.get("business_model", "")        if isinstance(n7, dict) else "",
            "is_unlocked":      r["id"] in paid_pids,
            "analysis_preview": n2.get("summary", "")               if isinstance(n2, dict) else "",
            "investor_verdict": n2.get("investor_verdict", "")      if isinstance(n2, dict) else "",
            "created_at":       r["created_at"],
            # Preview panel data — embedded upfront, zero extra fetch
            "n1": {
                "problem":              n1.get("problem", "")              if isinstance(n1, dict) else "",
                "solution":             n1.get("solution", "")             if isinstance(n1, dict) else "",
                "target_market":        n1.get("target_market", "")        if isinstance(n1, dict) else "",
                "market_size":          n1.get("market_size", "")          if isinstance(n1, dict) else "",
                "competitive_advantage":n1.get("competitive_advantage", "") if isinstance(n1, dict) else "",
                "revenue_model":        n1.get("revenue_model", "")        if isinstance(n1, dict) else "",
                "traction":             n1.get("traction", "")             if isinstance(n1, dict) else "",
                "team":                 n1.get("team", "")                 if isinstance(n1, dict) else "",
                "funding_ask":          n1.get("funding_ask", "")          if isinstance(n1, dict) else "",
                "product_stage":        n1.get("product_stage", "")        if isinstance(n1, dict) else "",
            },
            "n3": {
                "strengths":     (n3.get("strengths", [])     if isinstance(n3, dict) else [])[:3],
                "weaknesses":    (n3.get("weaknesses", [])    if isinstance(n3, dict) else [])[:2],
                "opportunities": (n3.get("opportunities", []) if isinstance(n3, dict) else [])[:3],
                "challenges":    (n3.get("challenges", [])    if isinstance(n3, dict) else [])[:2],
            },
            "n8_competitors": (n8.get("direct_competitors", []) if isinstance(n8, dict) else [])[:3],
        })

    total     = len(pitches_list)
    unlocked  = len([p for p in pitches_list if p["is_unlocked"]])
    avg_score = round(sum(p["score"] for p in pitches_list) / total) if total else 0

    stats = {
        "totalPitches":  total,
        "unlockedDeals": unlocked,
        "avgScore":      avg_score,
        "investments":   unlocked * 5000,
    }
    history = get_fn_history(uid)
    notifs  = get_notifications(uid)
    con.close()

    return render_template(
        "investor_dashboard.html",
        pitches=json.dumps(pitches_list),
        stats=json.dumps(stats),
        unlocked_ids=json.dumps(paid_pids),
        history_json=json.dumps(history),
        notifs_json=json.dumps(notifs),
        profile_json=json.dumps(profile_dict),
        fn_meta=json.dumps(FN_META),
        user_name=session.get("name", "Investor"),
        user_id=uid,
    )

# ─────────────────────────────────────────────
#  ROUTE: investor — pitch detail page
# ─────────────────────────────────────────────
@app.route("/investor/pitch/<int:pid>")
def investor_pitch_detail(pid):
    if session.get("role") != "investor":
        abort(403)
    uid = session["uid"]
    con = db()

    paid = con.execute(
        "SELECT id FROM payments WHERE investor_id=? AND pitch_id=? AND status='SUCCESS'",
        (uid, pid)
    ).fetchone()

    row = con.execute(
        "SELECT p.*, u.name as founder_name, u.email as founder_email "
        "FROM pitches p LEFT JOIN users u ON p.user_id=u.id "
        "WHERE p.id=? AND p.status='ACTIVE'",
        (pid,)
    ).fetchone()

    if not row:
        con.close()
        abort(404)

    pitch        = dict(row)
    analysis     = json.loads(pitch.get("analysis") or "{}")
    is_unlocked  = bool(paid)
    history      = get_fn_history(uid, pitch_id=pid)
    notifs       = get_notifications(uid)
    profile      = con.execute(
        "SELECT * FROM investor_profiles WHERE user_id=?", (uid,)
    ).fetchone()
    profile_dict = dict(profile) if profile else {}
    con.close()

    return render_template(
        "investor_pitch_detail.html",
        pitch        = json.dumps(pitch),
        analysis     = json.dumps(analysis),
        is_unlocked  = is_unlocked,
        pid          = pid,
        history_json = json.dumps(history),
        notifs_json  = json.dumps(notifs),
        profile_json = json.dumps(profile_dict),
        fn_meta      = json.dumps(FN_META),
        user_name    = session.get("name", "Investor"),
        user_id      = uid,
    )

# ─────────────────────────────────────────────
#  ROUTE: investor — ai_match & thesis (redirect to dashboard)
# ─────────────────────────────────────────────
@app.route("/investor/ai_match")
def investor_ai_match():
    if session.get("role") != "investor":
        abort(403)
    return redirect("/investor")

@app.route("/investor/thesis", methods=["GET", "POST"])
def investor_thesis_page():
    if session.get("role") != "investor":
        abort(403)
    return redirect("/investor")

# ─────────────────────────────────────────────
#  ROUTE: payment alias  /payment/<pid> → /pay/<pid>
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
#  API: investor — run nodes 13-25
# ─────────────────────────────────────────────
@app.route("/api/investor/analyze/<int:pid>/<int:node>", methods=["POST"])
def investor_analyze(pid, node):
    if session.get("role") != "investor":
        abort(403)
    if node not in range(13, 26):
        abort(400)
    uid = session["uid"]
    con = db()

    paid = con.execute(
        "SELECT id FROM payments WHERE investor_id=? AND pitch_id=? AND status='SUCCESS'",
        (uid, pid)
    ).fetchone()
    if not paid:
        con.close()
        return jsonify({"error": "Unlock this pitch first to run investor analysis."}), 403

    row = con.execute("SELECT * FROM pitches WHERE id=?", (pid,)).fetchone()
    if not row:
        con.close()
        abort(404)

    body       = request.get_json(silent=True) or {}
    pitch_text = row["raw_text"]

    if node == 14:
        thesis  = body.get("thesis", "General VC investing in Indian startups")
        context = f"Investor Thesis: {thesis}\nStartup Pitch: {pitch_text}"
    elif node == 25:
        amount  = body.get("amount", "Rs2 crore")
        stake   = body.get("stake", "15%")
        context = f"Investment Amount: {amount}, Stake: {stake}, Startup: {pitch_text}"
    elif node == 19:
        portfolio = body.get("portfolio", "No existing portfolio provided")
        context   = f"Investor Portfolio: {portfolio}\nNew Startup: {pitch_text}"
    else:
        context = pitch_text

    try:
        resp   = client.models.generate_content(model=MODEL, contents=PROMPTS[node](context))
        parsed = safe_json_parse(resp.text)
        con.close()
        save_fn_history(uid, pid, node, parsed)
        return jsonify({"success": True, "data": parsed, "node": node})
    except Exception as e:
        con.close()
        return jsonify({"success": False, "error": str(e)}), 500

# ─────────────────────────────────────────────
#  API: investor — save / get thesis
# ─────────────────────────────────────────────
@app.route("/api/investor/thesis", methods=["GET", "POST"])
def investor_thesis():
    if session.get("role") != "investor":
        abort(403)
    uid = session["uid"]
    con = db()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        con.execute("""
            INSERT INTO investor_profiles
              (user_id, thesis, industries, stage, ticket_min, ticket_max, geography, updated_at)
            VALUES (?,?,?,?,?,?,?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
              thesis=excluded.thesis,
              industries=excluded.industries,
              stage=excluded.stage,
              ticket_min=excluded.ticket_min,
              ticket_max=excluded.ticket_max,
              geography=excluded.geography,
              updated_at=CURRENT_TIMESTAMP
        """, (uid,
              data.get("thesis", ""),
              data.get("industries", ""),
              data.get("stage", "Seed"),
              int(data.get("ticket_min", 0) or 0),
              int(data.get("ticket_max", 0) or 0),
              data.get("geography", "")))
        con.commit()
        con.close()
        return jsonify({"ok": True})
    row = con.execute("SELECT * FROM investor_profiles WHERE user_id=?", (uid,)).fetchone()
    con.close()
    return jsonify(dict(row) if row else {})

# ─────────────────────────────────────────────
#  API: investor — smart filter (Fn 13)
# ─────────────────────────────────────────────
@app.route("/api/investor/smart_filter", methods=["POST"])
def smart_filter():
    if session.get("role") != "investor":
        abort(403)
    uid  = session["uid"]
    body = request.get_json(silent=True) or {}
    con  = db()

    profile = con.execute(
        "SELECT * FROM investor_profiles WHERE user_id=?", (uid,)
    ).fetchone()
    thesis = (profile["thesis"] if profile else "") or body.get("thesis", "General VC in India")

    rows = con.execute(
        "SELECT id,title,raw_text,score,category FROM pitches WHERE status='ACTIVE' ORDER BY score DESC LIMIT 20"
    ).fetchall()
    con.close()

    pitch_list = [
        {"id": r["id"], "title": r["title"], "summary": r["raw_text"][:200],
         "score": r["score"], "category": r["category"]}
        for r in rows
    ]
    context = f"Investor Thesis: {thesis}\nStartup List: {json.dumps(pitch_list)}"
    try:
        resp   = client.models.generate_content(model=MODEL, contents=PROMPTS[13](context))
        parsed = safe_json_parse(resp.text)
        save_fn_history(uid, 0, 13, parsed)
        return jsonify({"success": True, "data": parsed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─────────────────────────────────────────────
#  API: investor — send email (from Fn 23 output)
# ─────────────────────────────────────────────
@app.route("/api/investor/send_email", methods=["POST"])
def investor_send_email():
    if session.get("role") != "investor":
        abort(403)
    data     = request.get_json(silent=True) or {}
    to_email = data.get("to_email", "")
    subject  = data.get("subject", "DreamLaunch — Investor Message")
    body     = data.get("body", "")
    if not to_email:
        return jsonify({"error": "No recipient email provided."}), 400
    send_email_html(
        to_email, subject,
        f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:32px">
        <div style="background:#2563eb;color:#fff;padding:16px 24px;border-radius:8px 8px 0 0">
          <b style="font-size:18px">DreamLaunch</b>
        </div>
        <div style="border:1px solid #e2e8f0;border-top:none;padding:24px;border-radius:0 0 8px 8px">
          <p style="white-space:pre-line;line-height:1.7;color:#334155">{body}</p>
          <hr style="margin:20px 0;border:none;border-top:1px solid #e2e8f0">
          <p style="font-size:12px;color:#94a3b8">Sent via DreamLaunch — AI Venture Platform</p>
        </div></div>"""
    )
    return jsonify({"ok": True})

# ─────────────────────────────────────────────
#  PAYMENT
# ─────────────────────────────────────────────
@app.route("/payment/<int:pid>")
@app.route("/pay/<int:pid>")
def pay(pid):
    if session.get("role") != "investor":
        abort(403)
    order = str(uuid.uuid4())
    con   = db()
    con.execute(
        "INSERT INTO payments (investor_id,pitch_id,order_id,amount,status) VALUES (?,?,?,?,?)",
        (session["uid"], pid, order, 5000, "PENDING")
    )
    con.commit()
    pitch = con.execute("SELECT title FROM pitches WHERE id=?", (pid,)).fetchone()
    con.close()
    return render_template(
        "payment.html",
        order=order, amount=5000, pid=pid,
        pitch_title=pitch["title"] if pitch else f"Pitch #{pid}"
    )

# ─────────────────────────────────────────────
#  API: UPI confirm — creates order & marks SUCCESS
#  Called by investor_dashboard.html doPay()
# ─────────────────────────────────────────────
@app.route("/api/payment/upi_confirm", methods=["POST"])
def upi_confirm():
    if session.get("role") != "investor":
        abort(403)
    data = request.get_json(silent=True) or {}
    upi  = data.get("upi_id", "").strip()

    # Cast pid to int defensively — JSON can send numbers as strings
    try:
        pid = int(data.get("pid") or 0)
    except (ValueError, TypeError):
        pid = 0

    if not pid or not upi or "@" not in upi:
        return jsonify({"ok": False, "error": "Invalid request"}), 400

    uid = session["uid"]
    con = db()
    try:
        # Check if already paid — avoid duplicate rows
        existing = con.execute(
            "SELECT order_id FROM payments WHERE investor_id=? AND pitch_id=? AND status='SUCCESS'",
            (uid, pid)
        ).fetchone()
        if existing:
            con.close()
            return jsonify({"ok": True, "order": existing["order_id"], "already_paid": True})

        # Create a new order and mark it SUCCESS immediately
        order = str(uuid.uuid4())
        con.execute(
            "INSERT INTO payments (investor_id,pitch_id,order_id,amount,status) VALUES (?,?,?,?,?)",
            (uid, pid, order, 5000, "SUCCESS")
        )
        con.commit()

        # Fetch pitch title while connection is open, then CLOSE before add_notification.
        # Closing releases the shared read lock so add_notification's write
        # connection can acquire its exclusive lock without a "database is locked" error.
        pitch_row   = con.execute("SELECT title FROM pitches WHERE id=?", (pid,)).fetchone()
        pitch_title = pitch_row["title"] if pitch_row else f"Pitch #{pid}"
        con.close()

        add_notification(
            uid,
            "Pitch Unlocked 🔓",
            f"You have unlocked '{pitch_title}'. All 13 AI investor tools are now available.",
            "success"
        )
        return jsonify({"ok": True, "order": order})

    except Exception as e:
        try:
            con.close()
        except Exception:
            pass
        print(f"upi_confirm error: {e}")
        return jsonify({"ok": False, "error": "Payment processing failed. Please try again."}), 500


@app.route("/payment/success/<order>")
def payment_success(order):
    con = db()
    # Only notify if the row was NOT already SUCCESS (i.e. upi_confirm hasn't run yet)
    existing = con.execute(
        "SELECT status, investor_id, pitch_id FROM payments WHERE order_id=?", (order,)
    ).fetchone()
    already_done = existing and existing["status"] == "SUCCESS"

    con.execute("UPDATE payments SET status='SUCCESS' WHERE order_id=?", (order,))
    con.commit()

    if not already_done and existing:
        pitch = con.execute(
            "SELECT title FROM pitches WHERE id=?", (existing["pitch_id"],)
        ).fetchone()
        pitch_title = pitch["title"] if pitch else "a pitch"
        investor_id = existing["investor_id"]
        con.close()    # release lock BEFORE opening second write connection in add_notification
        add_notification(
            investor_id,
            "Pitch Unlocked 🔓",
            f"You have unlocked '{pitch_title}'. All 13 AI investor tools are now available.",
            "success"
        )
    else:
        con.close()
    return redirect("/investor")

# ─────────────────────────────────────────────
#  ROUTES: MESSAGING
# ─────────────────────────────────────────────
@app.route("/messages")
def messages_home():
    if "uid" not in session:
        abort(403)
    uid  = session["uid"]
    role = session.get("role", "")
    con  = db()

    if role == "innovator":
        convs = con.execute("""
            SELECT DISTINCT p.id as pitch_id, p.title, p.raw_text,
              (SELECT COUNT(*) FROM messages m2
               WHERE m2.pitch_id=p.id AND m2.receiver_id=? AND m2.is_read=0) as unread
            FROM pitches p WHERE p.user_id=?
        """, (uid, uid)).fetchall()
    else:
        convs = con.execute("""
            SELECT DISTINCT p.id as pitch_id, p.title, p.raw_text,
              (SELECT COUNT(*) FROM messages m2
               WHERE m2.pitch_id=p.id AND m2.receiver_id=? AND m2.is_read=0) as unread
            FROM messages m
            JOIN pitches p ON m.pitch_id=p.id
            WHERE m.sender_id=? OR m.receiver_id=?
        """, (uid, uid, uid)).fetchall()

    con.close()
    return render_template(
        "messages.html",
        convs_json=json.dumps([dict(c) for c in convs]),
        messages_json=json.dumps([]),
        uid=uid,
        pid=0,
        pitch={},
        user_name=session.get("name", "User"),
        role=role,
    )

@app.route("/messages/<int:pid>", methods=["GET", "POST"])
def messages(pid):
    if "uid" not in session:
        abort(403)
    uid = session["uid"]
    con = db()

    if request.method == "POST":
        msg = request.form.get("msg", "").strip()
        if msg:
            pitch_row = con.execute(
                "SELECT user_id FROM pitches WHERE id=?", (pid,)
            ).fetchone()
            if pitch_row:
                owner    = pitch_row["user_id"]
                receiver = owner if uid != owner else int(request.form.get("to", owner))
                con.execute(
                    "INSERT INTO messages (pitch_id,sender_id,receiver_id,message) VALUES (?,?,?,?)",
                    (pid, uid, receiver, msg)
                )
                con.commit()
        con.close()
        return redirect(f"/messages/{pid}")

    msgs  = con.execute("""
        SELECT m.*, u.name as sender_name
        FROM messages m JOIN users u ON m.sender_id=u.id
        WHERE m.pitch_id=? ORDER BY m.timestamp ASC
    """, (pid,)).fetchall()
    pitch = con.execute("SELECT * FROM pitches WHERE id=?", (pid,)).fetchone()

    # mark read
    con.execute(
        "UPDATE messages SET is_read=1 WHERE pitch_id=? AND receiver_id=?",
        (pid, uid)
    )
    con.commit()

    role  = session.get("role", "")
    if role == "innovator":
        convs = con.execute("""
            SELECT DISTINCT p.id as pitch_id, p.title, p.raw_text,
              (SELECT COUNT(*) FROM messages m2
               WHERE m2.pitch_id=p.id AND m2.receiver_id=? AND m2.is_read=0) as unread
            FROM pitches p WHERE p.user_id=?
        """, (uid, uid)).fetchall()
    else:
        convs = con.execute("""
            SELECT DISTINCT p.id as pitch_id, p.title, p.raw_text,
              (SELECT COUNT(*) FROM messages m2
               WHERE m2.pitch_id=p.id AND m2.receiver_id=? AND m2.is_read=0) as unread
            FROM messages m JOIN pitches p ON m.pitch_id=p.id
            WHERE m.sender_id=? OR m.receiver_id=?
        """, (uid, uid, uid)).fetchall()

    con.close()
    return render_template(
        "messages.html",
        convs_json=json.dumps([dict(c) for c in convs]),
        messages_json=json.dumps([dict(m) for m in msgs]),
        pid=pid,
        pitch=dict(pitch) if pitch else {},
        uid=uid,
        user_name=session.get("name", "User"),
        role=role,
    )

# API: messages (AJAX)
@app.route("/api/messages/<int:pid>")
def api_messages(pid):
    if "uid" not in session:
        abort(403)
    con  = db()
    msgs = con.execute("""
        SELECT m.*, u.name as sender_name
        FROM messages m JOIN users u ON m.sender_id=u.id
        WHERE m.pitch_id=? ORDER BY m.timestamp ASC
    """, (pid,)).fetchall()
    con.execute(
        "UPDATE messages SET is_read=1 WHERE pitch_id=? AND receiver_id=?",
        (pid, session["uid"])
    )
    con.commit()
    con.close()
    return jsonify([dict(m) for m in msgs])

# API: send message (AJAX)
@app.route("/api/messages/<int:pid>/send", methods=["POST"])
def api_send_message(pid):
    if "uid" not in session:
        abort(403)
    data   = request.get_json(silent=True) or {}
    msg    = data.get("message", "").strip()
    uid    = session["uid"]
    if not msg:
        return jsonify({"error": "Empty message"}), 400
    con       = db()
    pitch_row = con.execute("SELECT user_id FROM pitches WHERE id=?", (pid,)).fetchone()
    if not pitch_row:
        con.close()
        return jsonify({"error": "Pitch not found"}), 404
    owner    = pitch_row["user_id"]
    receiver = owner if uid != owner else int(data.get("to", owner))
    con.execute(
        "INSERT INTO messages (pitch_id,sender_id,receiver_id,message) VALUES (?,?,?,?)",
        (pid, uid, receiver, msg)
    )
    con.commit()
    con.close()
    return jsonify({"ok": True})

# ─────────────────────────────────────────────
#  ROUTES: ADMIN
# ─────────────────────────────────────────────
@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        abort(403)
    con = db()
    stats = {
        "users":          con.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "pitches":        con.execute("SELECT COUNT(*) FROM pitches").fetchone()[0],
        "active_pitches": con.execute("SELECT COUNT(*) FROM pitches WHERE status='ACTIVE'").fetchone()[0],
        "rejected":       con.execute("SELECT COUNT(*) FROM pitches WHERE status='REJECTED'").fetchone()[0],
        "flagged":        con.execute("SELECT COUNT(*) FROM pitches WHERE status='FLAGGED'").fetchone()[0],
        "payments":       con.execute("SELECT COUNT(*) FROM payments WHERE status='SUCCESS'").fetchone()[0],
        "innovators":     con.execute("SELECT COUNT(*) FROM users WHERE role='innovator'").fetchone()[0],
        "investors":      con.execute("SELECT COUNT(*) FROM users WHERE role='investor'").fetchone()[0],
        "revenue":        con.execute(
                              "SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='SUCCESS'"
                          ).fetchone()[0],
        "avg_score":      round(
                              con.execute("SELECT COALESCE(AVG(score),0) FROM pitches").fetchone()[0] or 0, 1
                          ),
        "monthly_submissions": [dict(r) for r in con.execute(
            "SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as cnt "
            "FROM pitches GROUP BY month ORDER BY month DESC LIMIT 8"
        ).fetchall()],
        "category_counts": [dict(r) for r in con.execute(
            "SELECT category, COUNT(*) as cnt, ROUND(AVG(score),1) as avg_score "
            "FROM pitches GROUP BY category ORDER BY cnt DESC LIMIT 10"
        ).fetchall()],
    }
    # Lean pitch list — NO analysis blob, NO raw_text
    all_pitches = con.execute(
        "SELECT p.id, p.title, p.score, p.category, p.status, p.created_at, "
        "       u.name as author_name, u.email as author_email "
        "FROM pitches p LEFT JOIN users u ON p.user_id=u.id "
        "ORDER BY p.id DESC LIMIT 300"
    ).fetchall()
    all_users = con.execute(
        "SELECT id, name, email, role, created_at FROM users ORDER BY id DESC"
    ).fetchall()
    all_payments = con.execute(
        "SELECT pay.id, pay.investor_id, pay.pitch_id, pay.order_id, pay.amount, pay.status, "
        "       u.name as investor_name "
        "FROM payments pay "
        "LEFT JOIN users u ON pay.investor_id=u.id "
        "ORDER BY pay.id DESC LIMIT 300"
    ).fetchall()
    notifs = get_notifications(session["uid"])
    con.close()

    return render_template(
        "admin_dashboard.html",
        stats=stats,
        pitches=json.dumps([dict(p) for p in all_pitches]),
        users=json.dumps([dict(u) for u in all_users]),
        payments=json.dumps([dict(p) for p in all_payments]),
        fn_meta=json.dumps(FN_META),
        user_name=session.get("name", "Admin"),
        user_id=session["uid"],
    )


# ─────────────────────────────────────────────
#  API: admin — single pitch detail (on demand)
# ─────────────────────────────────────────────
@app.route("/api/admin/pitch/<int:pid>")
def api_admin_pitch_detail(pid):
    if session.get("role") != "admin":
        abort(403)
    con = db()
    row = con.execute(
        "SELECT p.id, p.title, p.raw_text, p.score, p.category, p.status, "
        "       p.created_at, p.analysis, u.name as author_name, u.email as author_email "
        "FROM pitches p LEFT JOIN users u ON p.user_id=u.id "
        "WHERE p.id=?", (pid,)
    ).fetchone()
    con.close()
    if not row:
        abort(404)
    d = dict(row)
    try:
        analysis = json.loads(d.get("analysis") or "{}")
        d["n2"]  = analysis.get("node_2", {})
        d["n26"] = analysis.get("node_26", {})
        d["n1"]  = analysis.get("node_1", {})
    except Exception:
        d["n2"] = {}; d["n26"] = {}; d["n1"] = {}
    del d["analysis"]
    return jsonify(d)

@app.route("/admin/update_pitch/<int:pid>", methods=["POST"])
def admin_update_pitch(pid):
    if session.get("role") != "admin":
        abort(403)
    status = request.form.get("status", "ACTIVE")
    con    = db()
    con.execute("UPDATE pitches SET status=? WHERE id=?", (status, pid))
    con.commit()
    con.close()
    return jsonify({"ok": True})

# ─────────────────────────────────────────────
#  API: admin — run any function on any pitch
# ─────────────────────────────────────────────
@app.route("/api/admin/run/<int:pid>/<int:node>", methods=["POST"])
def admin_run(pid, node):
    if session.get("role") != "admin":
        abort(403)
    if node not in PROMPTS:
        abort(400)
    con = db()
    row = con.execute("SELECT * FROM pitches WHERE id=?", (pid,)).fetchone()
    if not row:
        con.close()
        abort(404)

    body    = request.get_json(silent=True) or {}
    context = row["raw_text"]

    if node == 28:
        prev_id   = body.get("compare_pid")
        prev_row  = con.execute(
            "SELECT raw_text FROM pitches WHERE id=?", (prev_id,)
        ).fetchone() if prev_id else None
        prev_text = prev_row["raw_text"] if prev_row else "No previous pitch to compare."
        context   = f"Pitch A (previous):\n{prev_text}\n\nPitch B (new):\n{context}"
    elif node == 30:
        stats_row = {
            "total_pitches": con.execute("SELECT COUNT(*) FROM pitches").fetchone()[0],
            "avg_score":     con.execute("SELECT COALESCE(AVG(score),0) FROM pitches").fetchone()[0],
            "categories":    [dict(r) for r in con.execute(
                "SELECT category, COUNT(*) as cnt FROM pitches GROUP BY category ORDER BY cnt DESC LIMIT 10"
            ).fetchall()],
        }
        context = json.dumps(stats_row)

    try:
        resp     = client.models.generate_content(model=MODEL, contents=PROMPTS[node](context))
        parsed   = safe_json_parse(resp.text)
        analysis = json.loads(row["analysis"] or "{}")
        analysis[f"node_{node}"] = parsed
        con.execute("UPDATE pitches SET analysis=? WHERE id=?",
                    (json.dumps(analysis), pid))
        con.commit()
        con.close()
        save_fn_history(session["uid"], pid, node, parsed)
        return jsonify({"success": True, "data": parsed, "node": node})
    except Exception as e:
        con.close()
        return jsonify({"success": False, "error": str(e)}), 500

# ─────────────────────────────────────────────
#  API: admin — platform trend analysis (Fn 30)
# ─────────────────────────────────────────────
@app.route("/api/admin/trends", methods=["POST"])
def admin_trends():
    if session.get("role") != "admin":
        abort(403)
    con = db()
    stats = {
        "total_pitches":       con.execute("SELECT COUNT(*) FROM pitches").fetchone()[0],
        "avg_score":           round(
                                   con.execute("SELECT COALESCE(AVG(score),0) FROM pitches").fetchone()[0] or 0, 1
                               ),
        "total_users":         con.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "revenue":             con.execute(
                                   "SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='SUCCESS'"
                               ).fetchone()[0],
        "categories":          [dict(r) for r in con.execute(
                                   "SELECT category, COUNT(*) as cnt, ROUND(AVG(score),1) as avg_score "
                                   "FROM pitches GROUP BY category ORDER BY cnt DESC LIMIT 10"
                               ).fetchall()],
        "monthly_submissions": [dict(r) for r in con.execute(
                                   "SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as cnt "
                                   "FROM pitches GROUP BY month ORDER BY month DESC LIMIT 6"
                               ).fetchall()],
    }
    con.close()
    try:
        resp   = client.models.generate_content(model=MODEL, contents=PROMPTS[30](json.dumps(stats)))
        parsed = safe_json_parse(resp.text)
        save_fn_history(session["uid"], 0, 30, parsed)
        return jsonify({"success": True, "data": parsed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─────────────────────────────────────────────
#  API: admin — bulk spam scan
# ─────────────────────────────────────────────
@app.route("/api/admin/spam_scan", methods=["POST"])
def admin_spam_scan():
    if session.get("role") != "admin":
        abort(403)
    con     = db()
    rows    = con.execute(
        "SELECT * FROM pitches WHERE status='ACTIVE' ORDER BY id DESC LIMIT 10"
    ).fetchall()
    results = []
    for row in rows:
        try:
            resp   = client.models.generate_content(model=MODEL, contents=PROMPTS[26](row["raw_text"]))
            parsed = safe_json_parse(resp.text)
            if isinstance(parsed, dict) and (parsed.get("is_spam") or parsed.get("is_scam")):
                con.execute("UPDATE pitches SET status='FLAGGED' WHERE id=?", (row["id"],))
            analysis = json.loads(row["analysis"] or "{}")
            analysis["node_26"] = parsed
            con.execute("UPDATE pitches SET analysis=? WHERE id=?",
                        (json.dumps(analysis), row["id"]))
            results.append({"id": row["id"], "result": parsed})
        except Exception as e:
            results.append({"id": row["id"], "error": str(e)})
    con.commit()
    con.close()
    return jsonify({"success": True, "results": results})

# ─────────────────────────────────────────────
#  API: get full pitch data (investor / admin)
# ─────────────────────────────────────────────
@app.route("/api/pitch_full/<int:pid>")
def api_pitch_full(pid):
    if "uid" not in session:
        abort(403)
    con = db()
    row = con.execute("SELECT * FROM pitches WHERE id=?", (pid,)).fetchone()
    con.close()
    if not row:
        abort(404)
    return jsonify(dict(row))

# ─────────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=False)
