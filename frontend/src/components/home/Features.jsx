import React from "react";
import { LuFileText, LuQuote, LuShield } from "react-icons/lu";

const features = [
  {
    Icon: LuFileText,
    iconBg: "bg-blue-50",
    color: "text-blue-600",
    title: "Upload Any Leaflet",
    description: "Simply upload a PDF of your medication's leaflet and start asking questions immediately.",
  },
  {
    Icon: LuQuote,
    iconBg: "bg-teal-50",
    color: "text-emerald-600",
    title: "Cited Answers",
    description: "Every answer includes direct quotes from the leaflet, so you can trust the source.",
  },
  {
    Icon: LuShield,
    iconBg: "bg-amber-50",
    color: "text-amber-600",
    title: "Grounded & Safe",
    description: "The assistant never invents information. If it's not in the leaflet, it will tell you.",
  },
];

export default function Features() {
  return (
    <section className="bg-gray-50 px-6 py-20">
      <h2 className="text-3xl font-bold text-gray-900 text-center mb-12">
        How It Works
      </h2>
      <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6">
        {features.map((f) => (
          <div key={f.title} className="bg-white border border-gray-100 rounded-2xl p-7 shadow-sm">
            <div className={`w-12 h-12 ${f.iconBg} rounded-xl flex items-center justify-center mb-5`}>
              <f.Icon className={`w-5 h-5 ${f.color}`} />
            </div>
            <p className="font-bold text-gray-900 text-base mb-2">{f.title}</p>
            <p className="text-sm text-gray-500 leading-relaxed">{f.description}</p>
          </div>
        ))}
      </div>
    </section>
  );
}