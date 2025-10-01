import express from "express";
import bodyParser from "body-parser";
import cors from "cors";
import axios from "axios";
import mysql2 from 'mysql2/promise';
import winston from 'winston';
const app = express();
const PORT = 5432;
const RoriPort = 8000;
const AthiniPort = 8001;
const PreshPort = 8002;
const StarCoderPort = 6000;


app.use(bodyParser.json());
app.use(cors());

// db connection
const logger = winston.createLogger({
    level: 'info',
    format: winston.format.json(),
    transports: [
        new winston.transports.File({ filename: 'database.log' }),
        new winston.transports.Console()
    ]
});

const db = mysql2.createPool({
    connectionLimit: 10,
    host: 'localhost',
    user: 'root',
    password: '',
    database: 'aitest'
});

db.getConnection((err, connection) => {
    if (err) {
        logger.error('Error getting connection from pool: ', err);
        return;
    }
    logger.info('Successfully obtained a connection from the pool');
    connection.release();
});

//------------------------------------------------------------------------------------------------------

let mistralResponse = {};
let aiResponse = {};

app.get("/", (req, res) => {
  if(req){
    console.log(req.body);
  }
  res.send("<h1>Hello, this is the main server!</h1>");
});
app.post("/api/changes", async (req, res) => {
  try {
    const { user_id, file_path, change_type, previousV, currentV } = req.body;

    if (!user_id || !file_path || !change_type || !previousV || !currentV) {
      return res.status(400).json({ error: "Missing required fields" });
    }

    // 1. Save to DB
    const [result] = await db.query(
      `INSERT INTO code_changes 
       (user_id, file_path, change_type, previousV, currentV) 
       VALUES (?, ?, ?, ?, ?)`,
      [user_id, file_path, change_type, previousV, currentV]
    );

    const record = {
      user_id,
      file_path,
      change_type,
      previousV,
      currentV,
      created_at: new Date(),
    };

    // 2. Call StarCoder for test cases
    const ApiStarCoder = `http://localhost:${StarCoderPort}/generate-testcases`;

    try {
      const response = await axios.post(ApiStarCoder, { record });
      aiResponse = response.data;
    } catch (err) {
      console.error("Error contacting StarCoder AI API:", err.message);
      aiResponse = { error: "StarCoder AI service unavailable" };
    }

    // 3. Forward record + AI response to Node.js Mistral service (/analyze)
    const mistralUrl = "http://localhost:7000/analyze";

    try {
      const forwardPayload = {
        record,
        aiResponse, // pass StarCoder test cases along
      };

      const miRes = await axios.post(mistralUrl, forwardPayload, {
        headers: { "Content-Type": "application/json" },
      });

      mistralResponse = miRes.data;
    } catch (err) {
      console.error("Error contacting Mistral service:", err.message);
      mistralResponse = { error: "Mistral service unavailable" };
    }

    // 4. Final response back to client
    res.json({
      message: "Change recorded successfully",
      record,
      aiResponse,
      mistralResponse,
    });
  } catch (error) {
    console.error("Error in /api/changes:", error);
    res.status(500).json({ error: "Server error" });
  }
});


// Get all changes with AI responses
app.get("/api/changes", async (req, res) => {
  try {
    // Join with users for context (optional)
    const [rows] = await db.query(
      `SELECT c.change_id, c.user_id, u.name AS user_name, 
              c.file_path, c.change_type, c.previousV, c.currentV, c.created_at
       FROM code_changes c
       JOIN users u ON c.user_id = u.user_id
       ORDER BY c.created_at DESC`
    );

    // For each change, we can (a) fetch StarCoder + Mistral live, or
    // (b) return only DB + let frontend request details lazily.
    // Let's do live fetch for simplicity.
    const results = [];
    for (const row of rows) {
      results.push({
        record: row,
        aiResponse,
        mistralResponse,
      });
    }

    res.json({
      message: "Fetched all code changes with AI analysis",
      changes: results,
    });
  } catch (err) {
    console.error("Error fetching changes:", err.message);
    res.status(500).json({ error: "Server error fetching changes" });
  }
});


app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});
