import { GoogleGenAI, Type } from "@google/genai";
import { AIRoutineSuggestion } from "../types";

const apiKey = process.env.API_KEY || '';

// Initialize generic client for safety, though we check key before calling
const ai = new GoogleGenAI({ apiKey });

export const generateRoutineSuggestion = async (prompt: string): Promise<AIRoutineSuggestion | null> => {
  if (!apiKey) {
    console.error("API Key missing");
    return null;
  }

  try {
    const modelId = "gemini-3-flash-preview"; 
    
    const response = await ai.models.generateContent({
      model: modelId,
      contents: `Generate a technical IT automation routine suggestion based on this request: "${prompt}". 
      Provide a professional title, a short description, a CRON expression for the schedule, and estimated runtime.`,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            title: { type: Type.STRING, description: "A professional title for the routine" },
            description: { type: Type.STRING, description: "Short description of what the automation does" },
            cronExpression: { type: Type.STRING, description: "Standard CRON expression" },
            estimatedDuration: { type: Type.STRING, description: "e.g., '2 mins', '45 sec'" }
          },
          required: ["title", "description", "cronExpression", "estimatedDuration"]
        }
      }
    });

    const text = response.text;
    if (!text) return null;
    
    return JSON.parse(text) as AIRoutineSuggestion;

  } catch (error) {
    console.error("Gemini API Error:", error);
    return null;
  }
};
