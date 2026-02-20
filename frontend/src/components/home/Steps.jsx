import React from "react";

const steps = [
  {
    number: 1,
    title: "Upload your PDF leaflet",
    description: "Drag & drop or click to upload the medication leaflet.",
  },
  {
    number: 2,
    title: "Ask your question",
    description: "Type or speak your question in plain language.",
  },
  {
    number: 3,
    title: "Get a cited answer",
    description: "Receive an accurate, referenced answer from the leaflet.",
  },
];

export default function Steps() {
  return (
    <section className="bg-stone-100/20 px-6 py-20">
      <h2 className="text-3xl font-bold text-gray-900 text-center mb-12">
        Get Started in 3 Steps
      </h2>
      <div className="max-w-lg mx-auto flex flex-col">
        {steps.map((step, index) => (
          <div key={step.number} className={`flex gap-5 ${index === 2 ? "mt-6" : ""}`}>
            <div className="flex flex-col items-center">
              <div
                className={`w-10 h-10 bg-blue-600 text-white font-bold text-sm flex items-center justify-center shrink-0
                  ${index === 2 ? "rounded-full" : "rounded-xl"}`}
              >
                {step.number}
              </div>
              {index < steps.length - 1 && (
                <div className="w-px flex-1 bg-gray-200 my-2" />
              )}
            </div>
            <div className="pb-10">
              <p className="font-bold text-gray-900 text-base">{step.title}</p>
              <p className="text-sm text-gray-500 mt-1">{step.description}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}