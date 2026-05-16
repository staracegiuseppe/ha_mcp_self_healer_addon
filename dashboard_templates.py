from typing import Any


def home_control_dashboard_template() -> dict[str, Any]:
    """Return a safe Lovelace sections dashboard skeleton for whole-home control."""
    return {
        "url_path": "codex-plancia",
        "title": "Codex Plancia",
        "icon": "mdi:tablet-dashboard",
        "method": (
            "Create a separate storage-mode Lovelace dashboard. Prefer native sections, "
            "tile cards, one-tap scene/script actions, and compact health cards so it works "
            "on wall tablets and phones without modifying the existing floorplan."
        ),
        "capability": "create_home_control_dashboard",
        "required_inputs": {
            "areas": "Home Assistant areas grouped by room/floor.",
            "entities": "Controllable light/switch/media/climate entities plus safety and health sensors.",
            "scripts": "Whole-home and room-level scripts such as spegni_tutta_casa or media controls.",
        },
        "sections": [
            {
                "title": "Centro comando",
                "purpose": "Global state, weather, temperature, power, and emergency whole-home actions.",
                "preferred_cards": ["heading", "tile", "button"],
            },
            {
                "title": "Stanze",
                "purpose": "Room-level lighting, media, climate, and presence grouped by area.",
                "preferred_cards": ["tile", "grid"],
            },
            {
                "title": "Sicurezza",
                "purpose": "Cameras, door/contact sensors, garage, alarm panels, and door release actions.",
                "preferred_cards": ["picture-entity", "tile", "button"],
            },
            {
                "title": "Salute casa",
                "purpose": "Unavailable entities, low batteries, backup status, Zigbee/MQTT health, and self-healer links.",
                "preferred_cards": ["tile", "entities"],
            },
        ],
    }
