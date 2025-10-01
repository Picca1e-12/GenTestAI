import express from "express";
import bodyParser from "body-parser";
import cors from "cors";
import OpenAI from "openai";

const app = express();
app.use(bodyParser.json());
app.use(cors());

const PORT = 7000;

const client = new OpenAI({
  apiKey:
    process.env.NVIDIA_API_KEY ||
    "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",
  baseURL: "https://integrate.api.nvidia.com/v1",
});

// Detect language & framework
function detectLanguage(filePath) {
  const ext = filePath.split(".").pop().toLowerCase();
  const languageMap = {
    js: "JavaScript",
    ts: "TypeScript",
    py: "Python",
    cs: "C#",
    java: "Java",
    go: "Go",
    rb: "Ruby",
    php: "PHP",
    cpp: "C++",
    c: "C",
  };
  return languageMap[ext] || "Unknown";
}

function detectFramework(language) {
  const frameworkMap = {
    JavaScript: "Jest",
    TypeScript: "Jest",
    Python: "pytest",
    "C#": "xUnit",
    Java: "JUnit",
    Go: "testing",
    Ruby: "RSpec",
    PHP: "PHPUnit",
  };
  return frameworkMap[language] || "standard";
}

app.get("/", (req, res) => {
  res.send("<h1>Hello, this is the Mistral service!</h1>");
});

app.post("/analyze", async (req, res) => {
  try {
    const { record, aiResponse } = req.body;

    if (!record) {
      return res.status(400).json({ error: "Missing code change record" });
    }

    const { file_path, change_type, previousV, currentV } = record;

    const language = detectLanguage(file_path);
    const framework = detectFramework(language);

    const prompt = `
Analyze this code change and generate test recommendations:

FILE: ${file_path}
LANGUAGE: ${language}
FRAMEWORK: ${framework}
CHANGE TYPE: ${change_type}
PREVIOUS: ${previousV}
CURRENT: ${currentV}

Return a JSON response with this exact structure:
{
  "risk_score": 1-10,
  "security_issues": ["issue1", "issue2"],
  "test_recommendations": [
    {
      "description": "Clear test description",
      "test_code": "Complete ${language} test code using ${framework}",
      "test_type": "unit|integration|security|performance",
      "priority": "high|medium|low"
    }
  ],
  "edge_cases": ["case1", "case2"],
  "framework": "${framework}"
}

If aiResponse test cases are provided, merge them as additional recommendations.
    `;

    const completion = await client.chat.completions.create({
      model: "mistralai/mistral-7b-instruct-v0.3",
      messages: [{ role: "user", content: prompt }],
      temperature: 0.2,
      top_p: 0.7,
      max_tokens: 1024,
      stream: false, // disable streaming here since we want JSON back
    });

    const rawText = completion.choices[0]?.message?.content?.trim();

    let analysisResult;
    try {
      const jsonStart = rawText.indexOf("{");
      const jsonEnd = rawText.lastIndexOf("}") + 1;
      const jsonString = rawText.slice(jsonStart, jsonEnd);
      analysisResult = JSON.parse(jsonString);
    } catch (err) {
      analysisResult = { error: "Could not parse JSON", raw: rawText };
    }

    // Merge StarCoder test cases if available
    if (aiResponse?.testCases?.length) {
      analysisResult.test_recommendations =
        analysisResult.test_recommendations || [];
      aiResponse.testCases.forEach((tc, idx) => {
        analysisResult.test_recommendations.push({
          description: tc.description || "StarCoder generated test",
          test_code: tc.input || "// no input provided",
          test_type: "unit",
          priority: "medium",
        });
      });
    }

    res.json({
      message: "Mistral analysis completed",
      analysisResult,
    });
  } catch (err) {
    console.error("Mistral service error:", err.message);
    res.status(500).json({ error: "Failed to analyze code change" });
  }
});

app.listen(PORT, () => {
  console.log(`Mistral Module API running on http://localhost:${PORT}`);
});
