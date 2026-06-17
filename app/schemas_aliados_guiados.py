from typing import Literal, TypedDict

ModoAnalisisAliados = Literal["automatico", "guiado"]

PerfilCliente = Literal[
    "publico_general",
    "familias",
    "estudiantes",
    "oficinistas",
    "transporte_publico",
    "compradores_paso",
    "salud_bienestar",
    "adultos_mayores",
]

HorarioPico = Literal["manana", "mediodia", "tarde", "noche_finde"]

TipoAtractor = Literal[
    "school",
    "transit_station",
    "bank",
    "shopping_mall",
    "supermarket",
    "convenience_store",
    "park",
    "doctor",
    "restaurant",
    "cafe",
    "gym",
    "pharmacy",
    "beauty_salon",
    "laundry",
]


class ConfiguracionAliadosGuiados(TypedDict, total=False):
    modo: ModoAnalisisAliados
    perfil_cliente: list[PerfilCliente]
    horarios_pico: list[HorarioPico]
    atractores_confirmados: list[TipoAtractor]


class SugerenciaAtractor(TypedDict):
    tipo: TipoAtractor
    etiqueta: str
    motivo: str
    explicacion: str
    sugerido: bool
    puntaje: int


class ResolucionAliadosGuiados(TypedDict):
    tipos_busqueda: list[TipoAtractor]
    fuente: Literal["guiado_usuario", "matriz_rubro", "categorias_usuario"]
    sugerencias: list[SugerenciaAtractor]
    configuracion: ConfiguracionAliadosGuiados
