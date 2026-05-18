
from typing import Optional

from pydantic import BaseModel, Field


class MaterialIn(BaseModel):
    item_type: str = "equipment"
    name: str = Field(..., min_length=1)
    characteristics: str = ""
    unit: str = ""
    price: float = Field(..., ge=0)
    source: str = ""


class MaterialUpdateIn(BaseModel):
    item_type: Optional[str] = None
    name: Optional[str] = Field(default=None, min_length=1)
    characteristics: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[float] = Field(default=None, ge=0)
    source: Optional[str] = None


class SmetaIn(BaseModel):
    parent_id: Optional[int] = None
    name: str = Field(..., min_length=1)
    customer_name: str = ""
    customer_details: str = ""
    contractor_name: str = ""
    contractor_details: str = ""
    approver_name: str = ""
    approver_details: str = ""
    tax_mode: str = "none"
    tax_rate: float = Field(0, ge=0, le=100)
    section_adjustments: dict = {}


class AuthIn(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class RegisterIn(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class ShareIn(BaseModel):
    email: str = Field(..., min_length=3)
    permission: str = "view"


class SmetaItemIn(BaseModel):
    item_type: str = "material"
    section: str = "Оборудование"
    name: str = Field(..., min_length=1)
    characteristics: str = ""
    unit: str = ""
    quantity: float = Field(1, gt=0)
    unit_price: float = Field(..., ge=0)
    source: str = ""


class AiSettingsIn(BaseModel):
    base_url: str = "https://api.vsegpt.ru/v1"
    api_key: str = ""
    model: str = ""
    assistant_prompt: str = ""


class AiCommandIn(BaseModel):
    prompt: str = Field(..., min_length=1)
    smeta_id: Optional[int] = None


class PriceImportResult(BaseModel):
    status: str
    imported: int
    skipped: int = 0


class LeadIn(BaseModel):
    phone: str
    source: str = ""


class QuoteIn(BaseModel):
    phone: str
    kind: str = "smeta"        # smeta | kp | callback
    payload: list = []         # cart items
    meta: dict = {}            # KP metadata
    total: float = 0
    source: str = ""


class PublicChatIn(BaseModel):
    phone: str               # the lead's phone, required for identification
    message: str = ""
    cart: list = []          # current cart for context
    mode: str = "smeta"      # smeta | support


class SeoPageIn(BaseModel):
    slug: str
    label: str = ""
    title: str = ""
    description: str = ""
    keywords: str = ""
    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    priority: str = "0.8"
    changefreq: str = "weekly"
    indexable: bool = True


class SiteSettingsIn(BaseModel):
    settings: dict


class TTSIn(BaseModel):
    text: str
    voice: str = ""
    sample_rate: int = 8000
    encoding: str = "LINEAR16"   # или MPEG_AUDIO для mp3


class VoiceDialogIn(BaseModel):
    """Высокоуровневый endpoint: одним запросом — распознать речь клиента,
    получить ответ AI, синтезировать обратно. Удобно для провайдеров, делающих
    'turn-in / turn-out' через webhook (например, custom-сценарий Voximplant)."""
    call_id: str
    caller_phone: str = ""
    transcript: str = ""    # если уже распознали — передаём текст; иначе можно audio_b64
    audio_b64: str = ""     # base64 mp3 (если transcript пустой)
    direction: str = "in"


class CallStartIn(BaseModel):
    call_id: str
    caller_phone: str
    direction: str = "in"   # in | out


class CallTurnIn(BaseModel):
    call_id: str
    transcript: str = ""


class CallEndIn(BaseModel):
    call_id: str
    duration_sec: int = 0
    recording_url: str = ""


class CallStatusIn(BaseModel):
    manager_status: str  # new | in_work | contacted | done | refused
