import json
from typing import Dict, Any, List, Tuple, Optional
from shapely.geometry import shape


# --------------------------------------------------
# Normalização
# --------------------------------------------------

def normalize_value(v: Any) -> Any:
    """Evita falsos positivos por tipo."""
    if isinstance(v, float):
        return round(v, 6)
    return v


def normalize_properties(props: Dict[str, Any], ignore_fields: List[str]) -> Dict[str, Any]:
    return {
        k: normalize_value(v)
        for k, v in props.items()
        if k not in ignore_fields
    }


# --------------------------------------------------
# Comparação de atributos
# --------------------------------------------------

def diff_properties(
    old_props: Dict[str, Any],
    new_props: Dict[str, Any],
    ignore_fields: List[str],
) -> List[Dict[str, Any]]:

    old_p = normalize_properties(old_props, ignore_fields)
    new_p = normalize_properties(new_props, ignore_fields)

    changes = []

    keys = set(old_p.keys()) | set(new_p.keys())

    for k in sorted(keys):
        old_v = old_p.get(k)
        new_v = new_p.get(k)

        if old_v != new_v:
            changes.append({
                "field": k,
                "old": old_v,
                "new": new_v,
            })

    return changes


# --------------------------------------------------
# Comparação geométrica REAL
# --------------------------------------------------

def geometry_diff(old_geom: Optional[Dict], new_geom: Optional[Dict]) -> Optional[Dict]:
    """
    Detecta mudança geométrica real.
    Retorna métricas humanas.
    """

    if not old_geom and not new_geom:
        return None

    if not old_geom or not new_geom:
        return {
            "changed": True,
            "reason": "geometry_added_or_removed"
        }

    try:
        g1 = shape(old_geom)
        g2 = shape(new_geom)

        if g1.equals(g2):
            return None

        distance = g1.hausdorff_distance(g2)

        return {
            "changed": True,
            "hausdorff_distance": round(distance, 3),
            "geom_type_old": g1.geom_type,
            "geom_type_new": g2.geom_type,
        }

    except Exception as e:
        return {
            "changed": True,
            "error": str(e)
        }


# --------------------------------------------------
# Auditoria completa de feature
# --------------------------------------------------

def audit_feature(
    old_feat: Dict[str, Any],
    new_feat: Dict[str, Any],
    ignore_fields: List[str],
) -> Dict[str, Any]:

    prop_changes = diff_properties(
        old_feat.get("properties", {}),
        new_feat.get("properties", {}),
        ignore_fields,
    )

    geom_change = geometry_diff(
        old_feat.get("geometry"),
        new_feat.get("geometry"),
    )

    return {
        "property_changes": prop_changes,
        "geometry_change": geom_change,
    }


# --------------------------------------------------
# Funções de log humano
# --------------------------------------------------

def format_feature_audit(fid: str, audit: Dict[str, Any]) -> List[str]:
    lines = []

    if audit["property_changes"]:
        lines.append(f"Registro {fid}")
        for ch in audit["property_changes"]:
            lines.append(
                f"  {ch['field']}: {ch['old']} → {ch['new']}"
            )

    if audit["geometry_change"]:
        g = audit["geometry_change"]
        lines.append(f"Registro {fid} (GEOMETRIA ALTERADA)")
        if "hausdorff_distance" in g:
            lines.append(
                f"  deslocamento máximo ≈ {g['hausdorff_distance']} m"
            )
        if "reason" in g:
            lines.append(f"  motivo: {g['reason']}")

    return lines
