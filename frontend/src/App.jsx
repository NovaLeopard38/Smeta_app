import { useState, useEffect } from "react";
import * as api from "./api";
import { useSmetas } from "./hooks/useSmetas";
import { useMaterials } from "./hooks/useMaterials";
import { useAI } from "./hooks/useAI";
import { useAdmin } from "./hooks/useAdmin";
import { money, isWorkMaterial, wholeQuantityInput, parentIdOf, hasManualPrice, compactDetails, hasLongDetails, buildSmetaTree, buildGroupedItems } from "./utils";
import { ThemeProvider } from "./context/ThemeContext";
import { AuthProvider, useAuthContext } from "./context/AuthContext";
import LoginForm from "./components/auth/LoginForm";
import TopBar from "./components/layout/TopBar";
import SmetaList from "./components/smetas/SmetaList";
import SmetaEditor from "./components/smetas/SmetaEditor";
import MaterialsPage from "./components/materials/MaterialsPage";
import AssistantPage from "./components/assistant/AssistantPage";
import AdminPage from "./components/admin/AdminPage";

function AppContent() {
  const [activePage, setActivePage] = useState("smetas");
  const [shellSearch, setShellSearch] = useState("");
  const [shellSearchSuggestions, setShellSearchSuggestions] = useState([]);
  const [shellSearchFocused, setShellSearchFocused] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const auth = useAuthContext();
  const { authToken, currentUser, setCurrentUser, setAuthToken } = auth;
  const sm = useSmetas(authToken, setMessage, setError);
  const mat = useMaterials(authToken, setMessage, setError);
  const ai = useAI(authToken, currentUser, setMessage, setError);
  const handleLogout = () => { auth.handleLogout(); sm.setSmetas([]); sm.setSelectedSmetaId(""); };
  const adm = useAdmin(authToken, currentUser, setCurrentUser, sm.selectedSmeta, setMessage, setError, handleLogout);

  const normMat = (data) => {
    if (Array.isArray(data)) return { items: data, total: data.length, has_more: false };
    return { items: data?.items || [], total: data?.total ?? (data?.items || []).length, has_more: Boolean(data?.has_more) };
  };

  useEffect(() => {
    if (!authToken) return;
    sm.loadSmetas(); ai.loadAiSettings(); mat.loadSections();
    api.getMe(authToken).then(r => setCurrentUser(r.data)).catch(() => { setAuthToken(""); setCurrentUser(null); });
  }, [authToken]); // eslint-disable-line

  useEffect(() => { if (authToken && currentUser?.is_admin) ai.loadAiSettings(); }, [authToken, currentUser?.is_admin]); // eslint-disable-line
  useEffect(() => { if (activePage === "admin" && !currentUser?.is_admin) setActivePage("smetas"); }, [activePage, currentUser?.is_admin]);

  useEffect(() => {
    if (!authToken || activePage !== "smetas") { sm.setItemSuggestions([]); return undefined; }
    const q = sm.itemForm.name.trim();
    if (q.length < 2) { sm.setItemSuggestions([]); return undefined; }
    const t = setTimeout(async () => { try { const r = await api.getMaterials(authToken, { q, item_type: "all", limit: 8 }); sm.setItemSuggestions(normMat(r.data).items); } catch (e) { sm.setItemSuggestions([]); } }, 180);
    return () => clearTimeout(t);
  }, [authToken, activePage, sm.itemForm.name]); // eslint-disable-line

  useEffect(() => {
    if (!authToken) { setShellSearchSuggestions([]); return undefined; }
    const q = shellSearch.trim();
    if (q.length < 2) { setShellSearchSuggestions([]); return undefined; }
    const t = setTimeout(async () => { try { const r = await api.getMaterials(authToken, { q, item_type: "all", limit: 8 }); setShellSearchSuggestions(normMat(r.data).items); } catch (e) { setShellSearchSuggestions([]); } }, 180);
    return () => clearTimeout(t);
  }, [authToken, shellSearch]); // eslint-disable-line

  const refreshData = async () => {
    const [r] = await Promise.all([api.getSmetas(authToken), mat.loadMaterials()]);
    sm.setSmetas(r.data);
    if (!sm.selectedSmetaId && r.data.length > 0) sm.setSelectedSmetaId(String(r.data[0].id));
  };

  const smetaTree = buildSmetaTree(sm.smetas, sm.expandedSmetaIds, sm.selectedSmetaId);
  const groupedItems = buildGroupedItems(mat.sections, sm.previewSmeta);
  const pageItems = [
    { id: "smetas", label: "Сметы", hint: sm.selectedSmeta ? sm.selectedSmeta.name : `${sm.smetas.length} смет` },
    { id: "prices", label: "Прайсы", hint: `${mat.materials.length} из ${mat.materialsTotal || mat.materials.length} позиций` },
    { id: "assistant", label: "AI Ассистент", hint: sm.selectedSmeta ? "работает с выбранной сметой" : "без выбранной сметы" },
    ...(currentUser?.is_admin ? [{ id: "admin", label: "Админка", hint: `${adm.adminUsers.length} пользователей` }] : []),
  ];
  const currentPageMeta = pageItems.find(p => p.id === activePage) || pageItems[0];
  const shellQ = shellSearch.trim().toLowerCase();
  const smetaSearchResults = shellQ.length >= 2
    ? sm.smetas.filter(s => { const t = (s.items || []).slice(0, 12).map(i => `${i.name || ""} ${i.characteristics || ""}`).join(" "); return [s.name, s.customer_name, s.contractor_name, s.approver_name, t].join(" ").toLowerCase().includes(shellQ); }).slice(0, 5) : [];
  const shellHasResults = smetaSearchResults.length > 0 || shellSearchSuggestions.length > 0;
  const handleShellSuggestionAdd = async (m) => { await sm.handleAddMaterialToSmeta(m); setShellSearch(""); setShellSearchSuggestions([]); setShellSearchFocused(false); };
  const handleShellSuggestionOpen = (m) => { const q = m.name || shellSearch.trim(); setShellSearch(q); mat.setMaterialQuery(q); setActivePage("prices"); setShellSearchFocused(false); };
  const handleShellSmetaOpen = (s) => { sm.setSelectedSmetaId(String(s.id)); setActivePage("smetas"); setShellSearch(""); setShellSearchSuggestions([]); setShellSearchFocused(false); };
  const handleShellSearchKeyDown = (e) => { if (e.key !== "Enter") return; e.preventDefault(); const q = shellSearch.trim(); if (q) { mat.setMaterialQuery(q); setActivePage("prices"); setShellSearchFocused(false); } };

  if (!authToken) {
    return <LoginForm onLogin={() => auth.handleLogin(setError, setMessage)} onRegister={() => auth.handleRegister(setError, setMessage)} message={message} error={error} />;
  }

  return (
    <main className="app-shell shell-layout h-layout">
      <div className="main-shell">
        <TopBar currentUser={currentUser} activePage={activePage} setActivePage={setActivePage} pageItems={pageItems} currentPageMeta={currentPageMeta} handleLogout={handleLogout} previewSmeta={sm.previewSmeta} money={money} shellSearch={shellSearch} setShellSearch={setShellSearch} shellSearchFocused={shellSearchFocused} setShellSearchFocused={setShellSearchFocused} shellHasResults={shellHasResults} smetaSearchResults={smetaSearchResults} shellSearchSuggestions={shellSearchSuggestions} handleShellSearchKeyDown={handleShellSearchKeyDown} handleShellSmetaOpen={handleShellSmetaOpen} handleShellSuggestionOpen={handleShellSuggestionOpen} handleShellSuggestionAdd={handleShellSuggestionAdd} parentIdOf={parentIdOf} isWorkMaterial={isWorkMaterial} />
        <main className="content">
          {(message || error) && <div className={error ? "notice error" : "notice"}>{error || message}</div>}
          {activePage === "smetas" && (
            <section className="workspace">
              <SmetaList smetas={sm.smetas} smetaTree={smetaTree} selectedSmetaId={sm.selectedSmetaId} setSelectedSmetaId={sm.setSelectedSmetaId} expandedSmetaIds={sm.expandedSmetaIds} setExpandedSmetaIds={sm.setExpandedSmetaIds} smetaName={sm.smetaName} setSmetaName={sm.setSmetaName} handleCreateSmeta={sm.handleCreateSmeta} money={money} parentIdOf={parentIdOf} />
              <SmetaEditor selectedSmeta={sm.selectedSmeta} previewSmeta={sm.previewSmeta} groupedItems={groupedItems} sections={mat.sections} smetaDetails={sm.smetaDetails} updateSmetaDetails={sm.updateSmetaDetails} updateSectionAdjustment={sm.updateSectionAdjustment} handleSaveSmetaDetails={sm.handleSaveSmetaDetails} shareForm={sm.shareForm} setShareForm={sm.setShareForm} handleShareSmeta={() => sm.handleShareSmeta(adm.loadAdminData)} handleBranchSmeta={sm.handleBranchSmeta} handleCheckSmeta={() => sm.handleCheckSmeta(ai.setAiResponse)} handleExportExcel={sm.handleExportExcel} handlePrintSmeta={sm.handlePrintSmeta} handleDeleteSmeta={sm.handleDeleteSmeta} itemForm={sm.itemForm} updateItemForm={sm.updateItemForm} itemSuggestions={sm.itemSuggestions} handleAddCustomItem={sm.handleAddCustomItem} handleAddSuggestedItem={sm.handleAddSuggestedItem} handleDeleteItem={sm.handleDeleteItem} updateItemDraft={sm.updateItemDraft} getItemDraft={sm.getItemDraft} commitItemDraft={sm.commitItemDraft} expandedItems={sm.expandedItems} toggleItem={sm.toggleItem} aiPrompt={ai.aiPrompt} setAiPrompt={ai.setAiPrompt} handleAiRequest={() => ai.handleAiRequest(sm.selectedSmeta, sm.setSmetas, sm.setSelectedSmetaId)} adminAccess={adm.adminAccess} adminBusy={adm.adminBusy} handleRevokeAccess={adm.handleRevokeAccess} currentUser={currentUser} money={money} isWorkMaterial={isWorkMaterial} wholeQuantityInput={wholeQuantityInput} hasManualPrice={hasManualPrice} compactDetails={compactDetails} hasLongDetails={hasLongDetails} />
            </section>
          )}
          {activePage === "prices" && (
            <MaterialsPage materials={mat.materials} materialsTotal={mat.materialsTotal} materialsHasMore={mat.materialsHasMore} materialsLoadingMore={mat.materialsLoadingMore} materialQuery={mat.materialQuery} setMaterialQuery={mat.setMaterialQuery} materialType={mat.materialType} setMaterialType={mat.setMaterialType} equipmentCategoryFilter={mat.equipmentCategoryFilter} setEquipmentCategoryFilter={mat.setEquipmentCategoryFilter} technologyFilter={mat.technologyFilter} setTechnologyFilter={mat.setTechnologyFilter} megapixelsFilter={mat.megapixelsFilter} setMegapixelsFilter={mat.setMegapixelsFilter} priceToFilter={mat.priceToFilter} setPriceToFilter={mat.setPriceToFilter} file={mat.file} setFile={mat.setFile} importMode={mat.importMode} setImportMode={mat.setImportMode} supplierUrl={mat.supplierUrl} setSupplierUrl={mat.setSupplierUrl} materialForm={mat.materialForm} updateMaterialForm={mat.updateMaterialForm} handleUpload={() => mat.handleUpload(refreshData)} handleCreateMaterial={() => mat.handleCreateMaterial(refreshData)} loadMoreMaterials={mat.loadMoreMaterials} loadAllMaterials={mat.loadAllMaterials} quantityByMaterial={sm.quantityByMaterial} setQuantityByMaterial={sm.setQuantityByMaterial} handleAddMaterialToSmeta={sm.handleAddMaterialToSmeta} money={money} isWorkMaterial={isWorkMaterial} wholeQuantityInput={wholeQuantityInput} />
          )}
          {activePage === "assistant" && (
            <AssistantPage selectedSmeta={sm.selectedSmeta} previewSmeta={sm.previewSmeta} aiPrompt={ai.aiPrompt} setAiPrompt={ai.setAiPrompt} aiResponse={ai.aiResponse} handleAiRequest={() => ai.handleAiRequest(sm.selectedSmeta, sm.setSmetas, sm.setSelectedSmetaId)} money={money} />
          )}
          {activePage === "admin" && currentUser?.is_admin && (
            <AdminPage currentUser={currentUser} adminUsers={adm.adminUsers} adminSelectedUserId={adm.adminSelectedUserId} adminUserSmetas={adm.adminUserSmetas} adminBusy={adm.adminBusy} selectedAdminUser={adm.selectedAdminUser} handleSelectAdminUser={adm.handleSelectAdminUser} handleToggleAdmin={adm.handleToggleAdmin} handleDeleteUser={adm.handleDeleteUser} aiSettings={ai.aiSettings} setAiSettings={ai.setAiSettings} apiKeyInput={ai.apiKeyInput} setApiKeyInput={ai.setApiKeyInput} models={ai.models} handleSaveAiSettings={ai.handleSaveAiSettings} handleLoadModels={ai.handleLoadModels} handleSelectModel={ai.handleSelectModel} modelPrice={ai.modelPrice} money={money} />
          )}
        </main>
      </div>
    </main>
  );
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
