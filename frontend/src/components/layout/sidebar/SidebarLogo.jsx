import { LuBriefcaseMedical } from "react-icons/lu";

export default function SidebarLogo() {
  return (
    <div className="flex items-center gap-3 px-6 py-4 border-b border-gray-100">
      <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center shrink-0">
        <LuBriefcaseMedical className="w-4 h-4 text-white" />
      </div>
      <div>
        <p className="font-bold text-gray-900 text-sm leading-none">MedAI</p>
        <p className="text-[10px] text-gray-400 tracking-widest mt-0.5">Your DocBot</p>
      </div>
    </div>
  );
}