"""
Configuration for the distributed CAD versioning system.
Topic 88: Versioning Distributed Objects - "Collaborative Design"
"""

# Site configuration
SITES = {
    "Site-A": {"host": "127.0.0.1", "port": 5001, "strategy": "branching"},
    "Site-B": {"host": "127.0.0.1", "port": 5002, "strategy": "branching"},
    "Site-C": {"host": "127.0.0.1", "port": 5003, "strategy": "branching"},
}

# Benchmark settings
BENCHMARK_VERSIONS = 10
BENCHMARK_COMPLEXITY = 5  # Number of vertex groups in generated geometry
BENCHMARK_CHANGE_RANGE = (0.05, 0.30)  # Min/max geometry change per version

# Storage paths
DATA_DIR = "data"
LOGS_DIR = "logs"
RESULTS_DIR = "results"
