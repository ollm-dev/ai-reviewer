Output Format Requirements:

1. All property names must use double quotes
2. All string values must use double quotes
3. All values wrapped with "{{}}" must be replaced with corresponding values from the project information, otherwise output "Sorry, insufficient information". You can consider these values as missing from the project information, and your goal is to supplement these values based on **other key-value pairs** and **project information**. **With one exception**: **Agent Familiarity** should not be filled based on project information, but based on your own knowledge base (very important)
4. Ensure the JSON format is completely correct
5. The generated JSON format should conform to the following structure, both structure and content must be complete, not just a partial segment
6. For each aiRecommendation in **textualEvaluations** below, your content needs to be very detailed, providing original text or detailed sentences for each argument, with word count between 500-800 words
7. All responses MUST be in English

Output example:

 {
  "formTitle": "Review Opinion Form",
  "projectInfo": {
    "projectTitle": "{{Extract project name}}",
    "projectType": "{{Extract project type}}",
    "researchField": "{{Extract research field}}",
    "applicantName": "{{Extract applicant name}}",
    "applicationId": "{{Extract application code}}"
  },

  "evaluationSections": [
    {
      "id": "applicantQualification",
      "title": "Agent Familiarity",
      "options": ["Familiar", "Somewhat Familiar", "Not Familiar"],
      "required": true,
      "aiRecommendation": "{{Your recommended answer is: one of the options}}",
      "aiReason": "{{Answer whether you are familiar or not familiar. For each review, the conference organizer asks us as reviewers, you can refer to yourself as a **reviewer**. Please indicate your familiarity with the paper you are reviewing, based on your own knowledge base. Do not reference **project information**. Few-shot example: As a reviewer who has long followed research in recommendation systems, user behavior analysis, and e-commerce, I have an in-depth understanding of the technical principles of interactive decision assistants, behavioral dynamics models, and NSFC project management requirements, meeting the professional field review requirements.}}"
    },
    {
      "id": "significance",
      "title": "Overall Evaluation",
      "options": ["Excellent", "Good", "Average", "Poor"],
      "required": true,
      "aiRecommendation": "{{Your recommended answer is: one of the options, for example: Excellent}}",
      "aiReason": "{{Cite original text evidence, for example: The project, based on health monitoring and emotional state analysis, has innovative public monitoring and guidance strategies that have a significant impact on current society.}}"
    },
    {
      "id": "relationshipExplanation",
      "title": "Funding Opinion",
      "description": "Please select the appropriate relationship description",
      "options": ["Priority Funding", "Fundable", "Not Recommended for Funding"],
      "required": true,
      "aiRecommendation": "{{Your recommended answer is: one of the options, for example: Priority Funding}}",
      "aiReason": "{{Cite original text evidence, for example: This research direction aligns with national key development directions and has strong social and scientific value.}}"
    }
  ],

  "textualEvaluations": [
    {
      "id": "scientificValue",
      "title": "Scientific Evaluation Description",
      "placeholder": "Please enter scientific evaluation description",
      "required": true,
      "aiRecommendation": "{{Recommendation of 500-800 words needed here}}",
      "minLength": 800
    },
    {
      "id": "socialDevelopment",
      "title": "Does the project meet economic and social development needs or address important scientific issues at the frontier of science?",
      "placeholder": "Please enter your evaluation opinion",
      "required": true,
      "aiRecommendation": "{{Recommendation of 500-800 words required here}}",
      "minLength": 800
    },
    {
      "id": "innovation",
      "title": "Please evaluate the innovation of the scientific issues described in the application and the academic value of the expected results",
      "placeholder": "Please enter your evaluation opinion",
      "required": true,
      "aiRecommendation": "{{Recommendation of 500-800 words required here}}",
      "minLength": 800
    },
    {
      "id": "feasibility",
      "title": "Please detail the research foundation and feasibility of the project. If possible, please suggest improvements to the research plan.",
      "placeholder": "Please enter your evaluation opinion",
      "required": true,
      "aiRecommendation": "{{Recommendation of 500-800 words required here}}",
      "minLength": 800
    },
    {
      "id": "otherSuggestions",
      "title": "Other Suggestions",
      "placeholder": "Please enter other suggestions",
      "required": false,
      "aiRecommendation": "{{Recommendation of 500-800 words required here}}",
      "minLength": 800
    }
  ]
}

# Note

1. Please do not output any extraneous text, only output JSON format that meets the requirements.
2. No need to use """ ``` """ backticks for wrapping, directly output JSON.
