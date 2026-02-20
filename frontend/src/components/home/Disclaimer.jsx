import React from "react";
import { LuTriangleAlert } from "react-icons/lu";

export default function Disclaimer() {
  return (
    <section className="px-6 py-8 bg-amber-50/50 border-t border-amber-100">
      <div className="max-w-2xl mx-auto text-center">
        <LuTriangleAlert className="w-5 h-5 text-amber-600 mx-auto mb-2" />
        <p className="text-xs text-amber-800 font-medium">Medical Disclaimer</p>
        <p className="text-[11px] text-amber-700 mt-1 leading-relaxed">
          This tool provides information based solely on uploaded medical leaflets. It is not a substitute
          for professional medical advice, diagnosis, or treatment. Always consult your healthcare provider.
        </p>
      </div>
    </section>
  );
}