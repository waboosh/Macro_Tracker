"""Client for the USDA FoodData Central API (https://fdc.nal.usda.gov/api-guide.html).

Used as a fallback in Add Entry when a food isn't found in the local database.
Requires a free API key from https://fdc.nal.usda.gov/api-key-signup.html, entered
in the Settings tab.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

# USDA nutrient numbers - stable identifiers, independent of nutrient name wording.
NUTRIENT_IDS = {
    "calories": 1008,  # Energy (kcal)
    "protein": 1003,   # Protein (g)
    "fat": 1004,       # Total lipid (fat) (g)
    "carbs": 1005,     # Carbohydrate, by difference (g)
}


class FdcApiError(Exception):
    """Raised when the USDA FoodData Central request fails or the key is invalid."""


def search_foods(api_key, query, page_size=15, timeout=10):
    """Search USDA FoodData Central for foods matching `query`.

    Returns a list of dicts: name, serving_size, serving_unit, calories, protein, carbs, fat.
    Raises FdcApiError on a missing/invalid key, network failure, or a bad response.
    """
    if not api_key:
        raise FdcApiError("No USDA FoodData Central API key set. Add one in the Settings tab.")
    if not query.strip():
        return []

    params = {
        "api_key": api_key,
        "query": query,
        "pageSize": page_size,
        "dataType": ["Foundation", "SR Legacy", "Branded"],
    }
    url = f"{SEARCH_URL}?{urllib.parse.urlencode(params, doseq=True)}"

    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise FdcApiError("USDA API rejected the key. Double-check it in the Settings tab.") from e
        raise FdcApiError(f"USDA API request failed (HTTP {e.code}).") from e
    except urllib.error.URLError as e:
        raise FdcApiError(f"Could not reach USDA FoodData Central: {e.reason}") from e
    except (ValueError, json.JSONDecodeError) as e:
        raise FdcApiError("USDA API returned an unexpected response.") from e

    results = []
    for food in data.get("foods", []):
        nutrients = {n.get("nutrientId"): n.get("value") for n in food.get("foodNutrients", [])}
        calories = nutrients.get(NUTRIENT_IDS["calories"])
        protein = nutrients.get(NUTRIENT_IDS["protein"])
        carbs = nutrients.get(NUTRIENT_IDS["carbs"])
        fat = nutrients.get(NUTRIENT_IDS["fat"])
        if None in (calories, protein, carbs, fat):
            continue  # skip entries missing a core macro

        serving_size = food.get("servingSize")
        serving_unit = food.get("servingSizeUnit")
        if not serving_size or not serving_unit:
            serving_size, serving_unit = 100, "g"  # USDA foods are reported per 100g by default

        results.append({
            "name": food.get("description", "Unknown food"),
            "serving_size": float(serving_size),
            "serving_unit": serving_unit,
            "calories": float(calories),
            "protein": float(protein),
            "carbs": float(carbs),
            "fat": float(fat),
        })
    return results
