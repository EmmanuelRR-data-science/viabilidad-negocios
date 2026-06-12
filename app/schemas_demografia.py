from typing import TypedDict


class PiramideGrupo(TypedDict):
    etiqueta: str
    mujeres: int
    hombres: int


class SegmentacionDemografica(TypedDict):
    fuente: str
    agebs_consultadas: int
    pob0_14: int
    pob15_64: int
    pob65_mas: int
    piramide: list[PiramideGrupo]
    pea: int
    pocupada: int
    pdesocup: int
    pe_inac: int
    p15a17a: int
    p18a24a: int
    p8a14an: int
