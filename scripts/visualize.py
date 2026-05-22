import os
import json
import matplotlib.pyplot as plt
import numpy as np

def generate_all_charts():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    results_dir = os.path.join(base_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    json_path = os.path.join(results_dir, "benchmark_results.json")
    
    if not os.path.exists(json_path):
        print(f"  [WARN] Không tìm thấy file JSON benchmark: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Styling
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["figure.facecolor"] = "#ffffff"
    plt.rcParams["axes.facecolor"] = "#f8fafc"
    
    versions = [f"v{i}" for i in range(1, data["num_versions"] + 1)]
    
    # 1. Chart: Individual Version Size comparison
    plt.figure(figsize=(10, 6))
    x = np.arange(len(versions))
    width = 0.35
    
    snapshot_kb = [s / 1024 for s in data["snapshot_sizes"]]
    delta_kb = [d / 1024 for d in data["delta_sizes"]]
    
    plt.bar(x - width/2, snapshot_kb, width, label="Kích thước Snapshot (Lưu toàn bộ)", color="#94a3b8")
    plt.bar(x + width/2, delta_kb, width, label="Kích thước Delta (Chỉ lưu vi sai)", color="#3b82f6")
    
    # Add annotations to show growth
    for i, v in enumerate(snapshot_kb):
        if i in [0, 5, 7, 8]:  # Highlight initial, redesign, branch A, branch B
            plt.text(i - width/2, v + 0.1, f"{v:.1f}KB", ha='center', va='bottom', fontsize=9, color="#475569")
    
    for i, v in enumerate(delta_kb):
        if i > 0 and v > 0.5: # Highlight big deltas
            plt.text(i + width/2, v + 0.1, f"{v:.1f}KB", ha='center', va='bottom', fontsize=9, color="#1d4ed8", fontweight="bold")
    
    plt.title("Biểu đồ 1: Thực tế Dung lượng từng Phiên bản (Có thêm/bớt chi tiết)", fontsize=14, fontweight="bold", pad=20, color="#1e293b")
    plt.xticks(x, versions)
    plt.xlabel("Phiên bản (Workflow thực tế)", fontsize=12, color="#475569")
    plt.ylabel("Kích thước File (KB)", fontsize=12, color="#475569")
    plt.legend(frameon=True, facecolor="#ffffff", edgecolor="#e2e8f0", fontsize=11)
    plt.tight_layout()
    plt.savefig(os.path.join(results_dir, "version_sizes.png"), dpi=200)
    plt.close()

    # 2. Chart: Cumulative Storage (Snapshot vs Delta)
    plt.figure(figsize=(10, 6))
    plt.plot(versions, [s / 1024 for s in data["cumulative_snapshot"]], label="Tổng tích lũy Snapshot", color="#ef4444", marker="o", linewidth=2.5)
    plt.plot(versions, [d / 1024 for d in data["cumulative_delta"]], label="Tổng tích lũy Delta", color="#3b82f6", marker="s", linewidth=2.5)
    plt.fill_between(versions, [d / 1024 for d in data["cumulative_delta"]], [s / 1024 for s in data["cumulative_snapshot"]], color="#3b82f6", alpha=0.1)
    
    plt.title("Biểu đồ 2: Đánh đổi Không Gian (Space Trade-off)", fontsize=14, fontweight="bold", pad=20, color="#1e293b")
    plt.xlabel("Phiên bản", fontsize=12, color="#475569")
    plt.ylabel("Tổng dung lượng ổ cứng bị chiếm dụng (KB)", fontsize=12, color="#475569")
    plt.legend(frameon=True, facecolor="#ffffff", edgecolor="#e2e8f0", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig(os.path.join(results_dir, "cumulative_storage.png"), dpi=200)
    plt.close()

    # 3. Chart: Rehydration Time vs Versions (The CPU Penalty)
    plt.figure(figsize=(10, 6))
    
    # We plot the theoretical O(k) cost (number of deltas) vs actual time
    costs = data["rehydration_costs"]
    times = data["rehydration_times_ms"]
    
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    color1 = '#059669'
    ax1.set_xlabel('Phiên bản (k)', fontsize=12, color="#475569")
    ax1.set_ylabel('Thời gian Rehydration thực tế (ms)', color=color1, fontsize=12)
    ax1.plot(versions, times, color=color1, marker='o', linewidth=2.5, label="Thời gian thực tế (ms)")
    ax1.tick_params(axis='y', labelcolor=color1)
    
    ax2 = ax1.twinx()
    color2 = '#94a3b8'
    ax2.set_ylabel('Độ phức tạp O(k) - Số lượng Delta phải ghép', color=color2, fontsize=12)
    ax2.bar(versions, costs, color=color2, alpha=0.3, width=0.5, label="Số lượng Delta (O(k))")
    ax2.tick_params(axis='y', labelcolor=color2)
    
    plt.title("Biểu đồ 3: Đánh đổi Thời Gian - Chi phí Rehydration O(k)", fontsize=14, fontweight="bold", pad=20, color="#1e293b")
    fig.tight_layout()
    plt.savefig(os.path.join(results_dir, "rehydration_latency.png"), dpi=200)
    plt.close()

    print("  [SUCCESS] Đã sinh 3 biểu đồ PNG phân tích thực tế tại results/")

if __name__ == "__main__":
    generate_all_charts()
