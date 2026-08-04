from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class GoogleLocationDTO(BaseModel):
    lat: float
    lng: float


class GoogleGeometryDTO(BaseModel):
    location: GoogleLocationDTO


class GooglePlaceItemDTO(BaseModel):
    place_id: str
    name: str
    rating: float | None = None
    user_ratings_total: int | None = None
    vicinity: str | None = None
    types: list[str] = Field(default_factory=list)
    geometry: GoogleGeometryDTO


class GoogleGeocodeAddressComponentDTO(BaseModel):
    long_name: str
    short_name: str
    types: list[str]


class GoogleGeocodeResultDTO(BaseModel):
    address_components: list[GoogleGeocodeAddressComponentDTO]
    formatted_address: str
    geometry: GoogleGeometryDTO
    place_id: str
    types: list[str]


class GoogleGeocodeResponseDTO(BaseModel):
    status: str
    results: list[GoogleGeocodeResultDTO] = Field(default_factory=list)

    @model_validator(mode="after")
    def validar_resultados_vacios(self) -> GoogleGeocodeResponseDTO:
        if self.status == "OK" and not self.results:
            self.status = "ZERO_RESULTS"
        return self
