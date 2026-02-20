import React, { useState } from "react";
import { Link } from "react-router-dom";
import { LuSparkles, LuMessageCircle, LuArrowRight, LuLock, LuZap } from "react-icons/lu";

export default function Hero() {
  const [leafletCount] = useState(0);
  const [questionCount] = useState(5);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-teal-50 flex items-start justify-center px-6 pt-16">
      <div className="max-w-3xl w-full text-center">

        <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-white/80 backdrop-blur border border-gray-200 rounded-full text-xs font-medium text-gray-500 mb-8">
          <LuSparkles />
          AI-Powered Medical Leaflet Assistant
        </div>

        <h1 className="text-4xl md:text-5xl font-extrabold text-gray-900 tracking-tight leading-tight mb-5">
          Understand Your{" "}
          <span
            style={{
              background: "linear-gradient(90deg, #2563eb, #0ea5e9)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            Medication
          </span>{" "}
          with Confidence
        </h1>

        <p className="text-base md:text-lg text-gray-500 leading-relaxed max-w-xl mx-auto mb-9">
          Upload your medication leaflet and ask questions in plain language. Get
          accurate, cited answers grounded entirely in the document.
        </p>
        <Link to="/chat">
          <button className="inline-flex items-center gap-2 h-12 px-6 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-xl shadow-lg shadow-blue-200 transition-colors cursor-pointer">
            <LuMessageCircle />
            
            Start a Conversation
            <LuArrowRight />
          </button>
        </Link>

        <div className="flex items-center justify-center gap-10 mt-14 pb-16">
          <div className="text-center">
            <div className="flex justify-center mb-1 p-1">
              <LuLock className="w-6 h-6 text-gray-500" />
            </div>
            <p className="text-xs text-gray-400">Private</p>
          </div>
          <div className="w-px h-8 bg-gray-200" />
          <div className="text-center">
            <div className="flex justify-center mb-1 p-1">
              <LuZap className="w-6 h-6 text-gray-500" />
            </div>
            <p className="text-xs text-gray-400">Instant</p>
          </div>
          <div className="w-px h-8 bg-gray-200" />
          <div className="text-center">
            <p className="text-2xl font-bold text-teal-600">100%</p>
            <p className="text-xs text-gray-400 mt-1">Grounded Answers</p>
          </div>

        </div>

      </div>
    </div>
  );
}