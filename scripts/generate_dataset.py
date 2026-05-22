import os
import json
import random

def generate_part(part_id, category, num_vertices=100):
    """Tao 1 doi tuong CAD mo phong."""
    vertices = []
    for idx in range(num_vertices):
        vertices.append({
            "id": f"V{idx + 1}",
            "x": round(random.uniform(-200, 200), 2),
            "y": round(random.uniform(-200, 200), 2),
            "z": round(random.uniform(-200, 200), 2)
        })
    
    edges = []
    for i in range(num_vertices):
        edges.append({
            "id": f"E{i + 1}",
            "from": vertices[i]["id"],
            "to": vertices[(i + 1) % num_vertices]["id"],
        })

    faces = []
    face_index = 1
    for i in range(0, num_vertices - 2, 3):
        faces.append({
            "id": f"F{face_index}",
            "edges": [edges[i]["id"], edges[(i + 1) % num_vertices]["id"], edges[(i + 2) % num_vertices]["id"]],
        })
        face_index += 1
    
    # Random properties dua tren category
    if category == "engine":
        material = "aluminum"
        weight = round(random.uniform(50, 150), 2)
    elif category == "chassis":
        material = "steel"
        weight = round(random.uniform(200, 500), 2)
    else:
        material = "plastic"
        weight = round(random.uniform(5, 30), 2)

    return {
        "part_id": part_id,
        "category": category,
        "geometry": {
            "type": "Solid",
            "vertices": vertices,
            "edges": edges,
            "faces": faces,
            "properties": {
                "category": category,
                "material": material,
                "tolerance_mm": 0.01,
                "weight_kg": weight
            }
        },
        "version": 1,
        "branch": "main",
        "site_origin": "Site-A" if category == "engine" else ("Site-B" if category == "chassis" else "Site-C")
    }

def main():
    # Set seed=42 de dam bao tinh tai lap (Reproducible) theo REQUIREMENTS.md
    random.seed(42)
    
    project_root = os.path.dirname(os.path.dirname(__file__))
    dataset_dir = os.path.join(project_root, "dataset")
    os.makedirs(dataset_dir, exist_ok=True)
    
    categories = [
        {"name": "engine", "prefix": "ENG", "site": "Site-A"},
        {"name": "chassis", "prefix": "CHS", "site": "Site-B"},
        {"name": "interior", "prefix": "INT", "site": "Site-C"}
    ]
    
    full_parts = []
    
    for cat in categories:
        cat_parts = []
        for i in range(1, 101):
            part_id = f"{cat['prefix']}-{i:03d}"
            part = generate_part(part_id, cat['name'])
            cat_parts.append(part)
            full_parts.append(part)
            
        # Luu dataset phan manh ngang (Horizontal Fragmentation)
        fragment_data = {
            "site_id": cat['site'],
            "category": cat['name'],
            "fragmentation": "horizontal",
            "predicate": f"category = '{cat['name']}'",
            "total": len(cat_parts),
            "parts": cat_parts
        }
        
        file_name = f"{cat['site'].lower().replace('-', '_')}_{cat['name']}.json"
        with open(os.path.join(dataset_dir, file_name), "w", encoding="utf-8") as f:
            json.dump(fragment_data, f, indent=2)
            
    # Luu Full Dataset de tham khao
    full_dataset = {
        "dataset_name": "CAD_Model Objects Dataset",
        "source": "generate_dataset.py",
        "total_parts": len(full_parts),
        "parts": full_parts
    }
    with open(os.path.join(dataset_dir, "full_dataset.json"), "w", encoding="utf-8") as f:
        json.dump(full_dataset, f, indent=2)
        
    print("Tao dataset thanh cong! Da luu vao thu muc dataset/")

if __name__ == "__main__":
    main()
