"""
YUCLAW Plugin System — extensible financial intelligence.
Anyone can build and share plugins.
"""
PLUGIN_REGISTRY = {}


def register(name, description, category='general'):
    def decorator(cls):
        PLUGIN_REGISTRY[name] = {
            'class': cls,
            'description': description,
            'category': category,
        }
        return cls
    return decorator


def list_plugins():
    print(f"\nYUCLAW Plugins ({len(PLUGIN_REGISTRY)} installed)")
    for name, info in PLUGIN_REGISTRY.items():
        print(f"  {name:25} [{info['category']:12}] {info['description']}")


def install_plugin(name: str):
    print(f"Installing {name}...")
    print(f"pip install yuclaw-{name}")
