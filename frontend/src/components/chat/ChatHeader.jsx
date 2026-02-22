import { LuFileText } from "react-icons/lu";

export default function ChatHeader({ fileName, pageCount }) {
  return (
    <div className="shrink-0 flex items-center gap-3 px-4 sm:px-6 py-4 bg-white border-b border-gray-100">
      <div className="lg:hidden w-9 shrink-0" />
      <LuFileText className="w-5 h-5 text-blue-600 shrink-0"/>
      <div className="min-w-0">
        <p className="font-semibold text-gray-900 text-sm truncate max-w-[160px] sm:max-w-xs">{fileName}</p>
        <p className="text-xs text-gray-400">
          {pageCount ? `${pageCount} pages · ` : ""}Grounded answers only
        </p>
      </div>
    </div>
  );
}