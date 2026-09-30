import React, { useState } from "react";

export const ModelSettings: React.FC = () => {
  const [provider, setProvider] = useState("ollama");
  const [modelName, setModelName] = useState("qwen2.5:7b");

  return (
    <div className="space-y-6">
      <div className="border-b border-gray-200 pb-5">
        <div className="flex items-center space-x-2 text-xs text-amber-700 bg-amber-100 border border-amber-300 px-2.5 py-1 rounded inline-flex mb-3">
          <span>🔒 Administrator Role Required (Wireframe Note)</span>
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-gray-900">Model settings</h2>
        <p className="text-sm text-gray-500 mt-1">
          Configure provider-independent LLM inference engine for semantic inference (FR-048/FR-049).
        </p>
      </div>

      <div className="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-r space-y-2">
        <p className="text-sm text-amber-800">
          <strong>Scaffold note:</strong> Model configuration wiring NOT STARTED. LLM provider configuration is a Level-3 concern (FR-048/FR-049).
        </p>
        <p className="text-xs text-amber-700">
          Credentials are stored in a credential manager later — never in the repo.
        </p>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 max-w-xl">
        <form onSubmit={(e) => e.preventDefault()} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              LLM Provider
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md border"
            >
              <option value="ollama">Ollama (Self-hosted / Local)</option>
              <option value="vllm">vLLM (Self-hosted)</option>
              <option value="openai">OpenAI compatible</option>
              <option value="anthropic">Anthropic</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">
              Interface is provider-independent via LiteLLM; provider is not locked.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Model Name / Identifier
            </label>
            <input
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder="e.g. qwen2.5:7b, llama3.1:8b"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>

          <div className="pt-2">
            <button
              type="button"
              disabled
              title="NOT STARTED"
              className="px-4 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-indigo-300 cursor-not-allowed"
            >
              Save Configuration (NOT STARTED)
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
