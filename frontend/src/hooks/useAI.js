import { useState } from "react";
import * as api from "../api";
import { formatError } from "./useAuth";

export function useAI(authToken, currentUser, setMessage, setError) {
  const [aiSettings, setAiSettings] = useState({
    base_url: "https://api.vsegpt.ru/v1",
    model: "",
    has_api_key: false,
    masked_api_key: "",
    assistant_prompt: "",
  });
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [models, setModels] = useState([]);
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiResponse, setAiResponse] = useState("");

  const runAction = async (action, successText) => {
    setError("");
    setMessage("");
    try {
      const actionMessage = await action();
      setMessage(actionMessage || successText);
    } catch (err) {
      setError(formatError(err));
    }
  };

  const loadAiSettings = async () => {
    if (!currentUser?.is_admin) {
      return;
    }
    try {
      const res = await api.getAISettings(authToken);
      setAiSettings(res.data);
    } catch (err) {
      setError("Не удалось загрузить настройки AI");
    }
  };

  const handleSaveAiSettings = async () => {
    await runAction(async () => {
      const res = await api.saveAISettings(authToken, {
        base_url: aiSettings.base_url,
        api_key: apiKeyInput,
        model: aiSettings.model,
        assistant_prompt: aiSettings.assistant_prompt || "",
      });
      setAiSettings(res.data);
      setApiKeyInput("");
    }, "Настройки AI сохранены");
  };

  const handleLoadModels = async () => {
    await runAction(async () => {
      const res = await api.getModels(authToken);
      setModels(res.data.models);
      if (!aiSettings.model && res.data.models.length > 0) {
        setAiSettings(current => ({ ...current, model: res.data.models[0].id }));
      }
    }, "Список моделей загружен");
  };

  const handleSelectModel = async (modelId) => {
    setAiSettings(current => ({ ...current, model: modelId }));
    await runAction(async () => {
      const res = await api.saveAISettings(authToken, {
        base_url: aiSettings.base_url,
        api_key: apiKeyInput,
        model: modelId,
      });
      setAiSettings(res.data);
    }, "Модель выбрана");
  };

  const handleAiRequest = async (selectedSmeta, setSmetas, setSelectedSmetaId) => {
    if (!aiPrompt.trim()) {
      setError("Введите запрос для ассистента");
      return;
    }
    await runAction(async () => {
      const res = await api.sendAICommand(authToken, {
        prompt: aiPrompt,
        smeta_id: selectedSmeta?.id || null,
      });
      setAiResponse([res.data.reply, ...(res.data.results || [])].join("\n"));
      setSmetas(res.data.smetas || []);
      if (res.data.selected_smeta_id) {
        setSelectedSmetaId(String(res.data.selected_smeta_id));
      }
    }, "Ассистент выполнил команду");
  };

  const modelPrice = (model) => {
    if (model.input_price == null && model.output_price == null) {
      return "стоимость не указана";
    }
    const input = model.input_price == null ? "?" : model.input_price;
    const output = model.output_price == null ? "?" : model.output_price;
    return `запрос: ${input} · ответ: ${output}`;
  };

  return {
    aiSettings,
    setAiSettings,
    apiKeyInput,
    setApiKeyInput,
    models,
    setModels,
    aiPrompt,
    setAiPrompt,
    aiResponse,
    setAiResponse,
    loadAiSettings,
    handleSaveAiSettings,
    handleLoadModels,
    handleSelectModel,
    handleAiRequest,
    modelPrice,
  };
}
