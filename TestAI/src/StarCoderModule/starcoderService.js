import express from "express";
import bodyParser from "body-parser";
import cors from "cors";
import OpenAI from "openai";
import mysql from "mysql2/promise"; 


const app = express();
app.use(bodyParser.json());
app.use(cors());

const PORT = 6000;

app.get("/", (req, res) => {
  if(req){
    console.log(req.body);
  }
  res.send("<h1>Hello, this is the Star Coder server!</h1>");
});


const client = new OpenAI({
  apiKey: process.env.NVIDIA_API_KEY || "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",
  baseURL: "https://integrate.api.nvidia.com/v1",
});

app.post("/generate-testcases", async (req, res) => {
  try {
    const { record } = req.body;

    if (!record) {
      return res.status(400).json({ error: "Missing code change record" });
    }

    const { file_path, change_type, previousV, currentV } = record;

    const isCodeFile = /\.(js|ts|py|java|cpp|c|cs)$/i.test(file_path);

    let prompt = "";

    if (isCodeFile) {
      prompt = `
You are an expert software tester. Generate detailed unit and integration test cases for the following code change.

File: ${file_path}
Change Type: ${change_type}
Previous Version: ${previousV}
Current Version: ${currentV}

Output the test cases in structured JSON format:
[
  { "id": 1, "description": "...", "input": "...", "expectedOutput": "..." }
]
      `;
    } else {
      prompt = `
You are an expert document validator and quality assurance specialist. Generate a detailed validation checklist and an audit report to verify the changes in the following business or QA document.

File: ${file_path}
Change Type: ${change_type}
Previous Version: ${previousV}
Current Version: ${currentV}

Output the validation steps in structured JSON format:
{
  "validation_checklist": [
    { "step": 1, "description": "...", "verification_method": "...", "status": "..." }
  ],
  "audit_report_summary": "..."
}
      `;
    }

    const completion = await client.completions.create({
      model: "bigcode/starcoder2-7b",
      prompt,
      temperature: 0.2,
      top_p: 0.7,
      max_tokens: 300,
      stream: false,
    });

    const rawText = completion.choices[0]?.text?.trim();

    let testCases = [];
    try {
      testCases = JSON.parse(rawText);
    } catch (e) {
      testCases = [{ id: 1, description: rawText }];
    }
	console.log(testCases);
    res.json({
      message: "Test cases generated successfully",
      testCases,
    });
  } catch (err) {
    console.error("StarCoder2 service error:", err.message);
    res.status(500).json({ error: "Failed to generate test cases" });
  }
});


app.listen(PORT, () => {
  console.log(`StarCoder2 Module API running on http://localhost:${PORT}`);
});
