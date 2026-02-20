import { LuFileText } from "react-icons/lu";

export default function ChatHeader({ fileName, pageCount }) {
  return (
    <div className="flex items-center gap-3 px-4 sm:px-6 py-4 bg-white border-b border-gray-100">
      <LuFileText className="w-5 h-5 text-blue-600 shrink-0" />
      <div>
        <p className="font-semibold text-gray-900 text-sm">{fileName}</p>
        <p className="text-xs text-gray-400">
          {pageCount ? `${pageCount} pages · ` : ""}Grounded answers only
        </p>
      </div>
    </div>
  );
}