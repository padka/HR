#!/usr/bin/env node
/**
 * Minimal MCP (Model Context Protocol) stdio server that exposes a Gemini text tool.
 *
 * This is intentionally dependency-free (no SDK) to keep setup simple:
 * - reads JSON-RPC messages from stdin (one JSON object per line)
 * - writes JSON-RPC responses to stdout (one JSON object per line)
 *
 * Env:
 * - GEMINI_API_KEY (required)
 * - GEMINI_MODEL (default: gemini-3-flash-preview)
 * - GEMINI_TIMEOUT_SECONDS (default: 30)
 */

import readline from "node:readline";

const API_KEY = process.env.GEMINI_API_KEY || "";
// Default to a fast Gemini 3.x model (v1beta listModels).
const DEFAULT_MODEL = (process.env.GEMINI_MODEL || "gemini-3-flash-preview").trim() || "gemini-3-flash-preview";
const TIMEOUT_SECONDS = Number.parseFloat(process.env.GEMINI_TIMEOUT_SECONDS || "30") || 30;

function send(obj) {
  process.stdout.write(`${JSON.stringify(obj)}\n`);
}

function ok(id, result) {
  send({ jsonrpc: "2.0", id, result });
}

function err(id, code, message, data) {
  const error = { code, message };
  if (data !== undefined) error.data = data;
  send({ jsonrpc: "2.0", id, error });
}

function asString(v) {
  if (typeof v === "string") return v;
  if (v === null || v === undefined) return "";
  return String(v);
}

function clampNumber(v, min, max, fallback) {
  const n = typeof v === "number" ? v : Number.parseFloat(String(v));
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, n));
}

function clampInt(v, min, max, fallback) {
  const n = typeof v === "number" ? v : Number.parseInt(String(v), 10);
  if (!Number.isFinite(n)) return fallback;
  const i = Math.trunc(n);
  return Math.min(max, Math.max(min, i));
}

async function geminiGenerate({ prompt, system, model, temperature, max_output_tokens }) {
  if (!API_KEY) {
    throw new Error("GEMINI_API_KEY is not set");
  }

  let finalModel = (asString(model).trim() || DEFAULT_MODEL).trim();
  // Accept both "gemini-*" and "models/gemini-*".
  if (finalModel.startsWith("models/")) finalModel = finalModel.slice("models/".length);
  const temp = clampNumber(temperature, 0, 2, 0.4);
  const maxOut = clampInt(max_output_tokens, 1, 8192, 1024);

  const userText = asString(prompt).trim();
  const systemText = asString(system).trim();

  const mergedText = systemText ? `${systemText}\n\n${userText}` : userText;
  if (!mergedText) {
    throw new Error("prompt is empty");
  }

  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(
    finalModel
  )}:generateContent?key=${encodeURIComponent(API_KEY)}`;

  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), Math.max(1, TIMEOUT_SECONDS) * 1000);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: mergedText }] }],
        generationConfig: {
          temperature: temp,
          maxOutputTokens: maxOut,
        },
      }),
      signal: controller.signal,
    });

    const raw = await res.text();
    let data = null;
    try {
      data = raw ? JSON.parse(raw) : null;
    } catch {
      data = null;
    }

    if (!res.ok) {
      const msg =
        (data && (data.error?.message || data.error?.status || data.error?.code)) ||
        raw ||
        `Gemini API error (${res.status})`;
      throw new Error(asString(msg));
    }

    const parts = data?.candidates?.[0]?.content?.parts || [];
    const text = parts
      .map((p) => (p && typeof p.text === "string" ? p.text : ""))
      .filter(Boolean)
      .join("");

    return text || "";
  } finally {
    clearTimeout(t);
  }
}

const tools = [
  {
    name: "gemini.generate",
    description: "Generate text using Google Gemini (for ideation, summarization, analysis).",
    inputSchema: {
      type: "object",
      properties: {
        prompt: { type: "string", description: "User prompt / input text." },
        system: { type: "string", description: "Optional system instructions (prepended to prompt)." },
        model: { type: "string", description: `Gemini model (default: ${DEFAULT_MODEL}).` },
        temperature: { type: "number", description: "0..2, default 0.4" },
        max_output_tokens: { type: "integer", description: "Max output tokens, default 1024" },
      },
      required: ["prompt"],
    },
  },
];

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });

rl.on("line", async (line) => {
  const trimmed = (line || "").trim();
  if (!trimmed) return;

  let msg;
  try {
    msg = JSON.parse(trimmed);
  } catch {
    return;
  }

  // Notifications have no id.
  const id = msg?.id;
  const method = msg?.method;
  const params = msg?.params || {};

  try {
    if (method === "initialize") {
      // Respond with minimal capabilities.
      const clientVersion = asString(params?.protocolVersion).trim() || "2025-06-18";
      ok(id, {
        protocolVersion: clientVersion,
        capabilities: { tools: { listChanged: false } },
        serverInfo: { name: "gemini-mcp", version: "0.1.0" },
        instructions:
          "Use gemini.generate for fast second opinions, ideation, and text analysis. Keep prompts concise; pass system for style constraints.",
      });
      return;
    }

    if (method === "ping") {
      ok(id, {});
      return;
    }

    if (method === "tools/list") {
      ok(id, { tools });
      return;
    }

    if (method === "tools/call") {
      const toolName = asString(params?.name);
      const args = params?.arguments || {};

      if (toolName !== "gemini.generate") {
        err(id, -32601, `Unknown tool: ${toolName}`);
        return;
      }

      let text = "";
      try {
        text = await geminiGenerate(args);
      } catch (e) {
        ok(id, {
          content: [{ type: "text", text: `Gemini error: ${asString(e?.message || e)}` }],
          isError: true,
        });
        return;
      }

      ok(id, { content: [{ type: "text", text }], isError: false });
      return;
    }

    // Ignore unhandled notifications/requests.
    if (id !== undefined) {
      err(id, -32601, `Method not found: ${asString(method)}`);
    }
  } catch (e) {
    if (id !== undefined) {
      err(id, -32603, "Internal error", { message: asString(e?.message || e) });
    }
  }
});

rl.on("close", () => {
  process.exit(0);
});
