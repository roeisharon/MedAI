import { LuTriangleAlert } from "react-icons/lu";

export default function SidebarDisclaimer() {
  return (
    <div className="px-4 py-4 border-t border-gray-100 bg-amber-50/50">
      <div className="flex gap-2">
        <LuTriangleAlert className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
        <p className="text-[10px] text-amber-700 leading-relaxed">
          This tool provides information from medical leaflets only. It does not replace professional medical advice.
        </p>
      </div>
    </div>
  );
}