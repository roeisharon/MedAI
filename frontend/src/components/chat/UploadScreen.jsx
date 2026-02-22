import { useRef, useState } from "react";
import { LuSparkles, LuUpload, LuFileText, LuTriangleAlert } from "react-icons/lu";

const parseError = (data) => {
  if (data?.user_message) return data.user_message;
  if (data?.detail)       return String(data.detail);
  return "An unexpected error occurred.";
};

const API = "/api";

export default function UploadScreen({ onChatCreated }) {
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver]   = useState(false);
  const [error, setError]         = useState(null);
  const inputRef = useRef(null);

  const handleFile = async (file) => {
    if (!file || file.type !== "application/pdf") return;
    setError(null);
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res  = await fetch(`${API}/chats`, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) { setError(parseError(data)); return; }
      onChatCreated?.(data);
    } catch {
      setError("Could not reach the backend. Is it running?");
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    handleFile(e.dataTransfer.files[0]);
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 sm:px-6 py-8">
      <div
        className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5"
        style={{ background: "linear-gradient(135deg, #eff6ff 0%, #f0fdf9 50%, #e0f2fe 100%)" }}
      >
        <LuSparkles className="w-7 h-7 text-blue-600" />
      </div>

      <h1 className="text-xl sm:text-2xl font-bold text-gray-900 mb-2 text-center">Medical Leaflet Assistant</h1>
      <p className="text-sm text-gray-500 text-center max-w-xs mb-8">
        Upload a medical leaflet to get accurate, grounded answers about your medication.
      </p>

      <div
        onClick={() => !uploading && inputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        className={`w-full max-w-full sm:max-w-md border-2 border-dashed rounded-2xl px-4 sm:px-8 py-8 sm:py-10 flex flex-col items-center justify-center transition-colors
          ${dragOver  ? "border-blue-400 bg-blue-50" : "border-gray-200"}
          ${uploading ? "cursor-default" : "cursor-pointer hover:border-blue-300 hover:bg-blue-50/40"}`}
      >
        {uploading ? (
          <>
            <div className="w-8 h-8 rounded-full border-2 border-gray-200 border-t-teal-500 animate-spin mb-3" />
            <p className="text-sm font-medium text-teal-600">Extracting leaflet content...</p>
          </>
        ) : (
          <>
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4"
              style={{ background: "linear-gradient(135deg, #eff6ff 0%, #f0fdf9 50%, #e0f2fe 100%)" }}
            >
              <LuUpload className="w-6 h-6 text-blue-600" />
            </div>
            <p className="font-semibold text-gray-900 text-sm mb-1">Upload Medical Leaflet</p>
            <p className="text-xs text-gray-400 mb-3">Drop your PDF here or click to browse</p>
            <div className="flex items-center gap-1.5 text-xs text-gray-400">
              <LuFileText className="w-3.5 h-3.5" />PDF files only
            </div>
          </>
        )}
      </div>

      {error && (
        <div className="mt-4 w-full sm:max-w-md flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          <LuTriangleAlert className="w-4 h-4 shrink-0 mt-0.5 text-red-500" />
          <span>{error}</span>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => handleFile(e.target.files[0])}
      />
    </div>
  );
}