import React, { useEffect, useState } from "react";
import axios from "axios";

// Simple UI components
const Card = ({ children }) => (
  <div className="bg-white shadow-md rounded-xl border border-gray-200 p-6">
    {children}
  </div>
);

const Badge = ({ children }) => (
  <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-blue-100 text-blue-700">
    {children}
  </span>
);

const Progress = ({ value }) => (
  <div className="w-full bg-gray-200 rounded-full h-2">
    <div
      className="bg-blue-500 h-2 rounded-full"
      style={{ width: `${value}%` }}
    />
  </div>
);

export default function Dashboard() {
  const [changes, setChanges] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await axios.get("http://localhost:5432/api/changes");
        console.log("Fetched changes:", res.data.changes);
        setChanges(res.data.changes || []);
      } catch (err) {
        console.error("Error fetching dashboard data:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  {/*if (loading) {
    return <p className="text-center mt-10">Loading dashboard...</p>;
  }*/}

  return (
    <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
      {changes.map((item, idx) => {
        const { record, aiResponse, mistralResponse } = item;
        const risk = mistralResponse?.analysisResult?.risk_score || Math.floor(Math.random() * 10) + 1;

        return (
          <Card key={idx}>
            {/* Header */}
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">{record.file_path}</h2>
              <Badge>{record.change_type}</Badge>
            </div>
            <p className="text-sm text-gray-600">
              Changed by:{" "}
              <strong>{record.user_name || `User ${record.user_id}`}</strong>
            </p>
            <p className="text-xs text-gray-500 mb-4">
              {new Date(record.created_at).toLocaleString()}
            </p>

            {/* Risk Score */}
            <div className="mb-4">
              <p className="text-sm font-medium mb-1">Risk Score: {risk}/10</p>
              <Progress value={(risk / 10) * 100} />
            </div>

            {/* StarCoder Test Cases */}
            <div className="mb-4">
              <h3 className="font-semibold text-sm mb-2">
                StarCoder Test Cases
              </h3>
              <ul className="list-disc list-inside text-sm text-gray-700">
                {aiResponse?.testCases?.map((tc, i) => (
                  <li key={i}>
                    <strong>{tc.description || "Test"}</strong> → expected:{" "}
                    {tc.expectedOutput || "N/A"}
                  </li>
                ))}
              </ul>
            </div>

            {/* Mistral Analysis */}
            <div>
              <h3 className="font-semibold text-sm mb-2">Mistral Analysis</h3>
              {mistralResponse?.analysisResult ? (
                <div className="text-sm text-gray-700">
                  <p className="mb-1">
                    <strong>Framework:</strong>{" "}
                    {mistralResponse.analysisResult.framework}
                  </p>
                  <p className="mb-1">
                    <strong>Security Issues:</strong>{" "}
                    {mistralResponse.analysisResult.security_issues.join(", ") ||
                      "None"}
                  </p>
                  <p className="mb-1">
                    <strong>Edge Cases:</strong>{" "}
                    {mistralResponse.analysisResult.edge_cases.join(", ") ||
                      "None"}
                  </p>
                </div>
              ) : (
                <p className="text-sm text-red-500">
                  No analysis available (service offline?)
                </p>
              )}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
