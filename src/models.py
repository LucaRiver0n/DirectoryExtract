from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class CompanyRecord:
    nombre_empresa: str = ""
    correo: str = ""
    telefono_1: str = ""
    telefono_2: str = ""
    direccion: str = ""
    estado: str = ""
    pais: str = ""
    sitio_web: str = ""
    linkedin: str = ""
    segmento: str = ""

    # Campos de control; se pueden excluir al exportar.
    ciudad: str = ""
    url_fuente: str = ""
    fuente_correo: str = ""
    fuente_telefono: str = ""
    fuente_sitio_web: str = ""
    fuente_linkedin: str = ""
    estado_extraccion: str = "OK"
    observaciones: str = ""

    def as_dict(self) -> dict:
        return asdict(self)

    def add_phone(self, phone: str) -> None:
        phone = clean_text(phone)
        if not phone:
            return
        current = [self.telefono_1, self.telefono_2]
        normalized = normalize_phone(phone)
        if any(normalize_phone(x) == normalized for x in current if x):
            return
        if not self.telefono_1:
            self.telefono_1 = phone
        elif not self.telefono_2:
            self.telefono_2 = phone

    def add_email(self, email: str) -> None:
        email = clean_text(email).lower().strip(".,;:()[]<>\"'")
        if email and not self.correo:
            self.correo = email


def clean_text(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("Â·", "·").split()).strip()


def normalize_phone(value: str | None) -> str:
    if not value:
        return ""
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits
