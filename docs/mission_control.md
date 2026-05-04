# Mission Control — SLAM / Positioning Module

Module de positionnement et tracking pour le robot UGV Waveshare.
Ajouté de façon non-destructive sur l'application Flask existante.

---

## Fichiers ajoutés

```
mission_control/
├── __init__.py          # Package marker
├── state.py             # Store position + trajectoire (thread-safe)
├── slam_adapter.py      # Adapter SLAM — mock / lidar_basic / slam
└── routes.py            # Blueprint Flask (routes API + page)

templates/
├── mission_control.html # Page principale
├── mission_control.js   # Canvas 2D, polling API, dessin
└── mission_control.css  # Styles thémés (CSS variables)

docs/
└── mission_control.md   # Cette doc
```

## Fichiers modifiés (changements minimaux)

| Fichier | Changement |
|---------|-----------|
| `app.py` | +4 lignes : import + `init_slam_adapter(base)` + `register_blueprint(mc_bp)` |
| `templates/index.html` | +1 lien MISSION dans la nav |
| `templates/admin.html` | +1 lien MISSION dans la nav |
| `templates/remote.html` | +1 lien MISSION dans la nav |
| `templates/photos.html` | +1 lien MISSION dans la nav |
| `templates/videos.html` | +1 lien MISSION dans la nav |
| `templates/settings.html` | +1 lien MISSION dans la nav |

---

## Lancer l'application

```bash
cd /path/to/ugv_rpi
python app.py
```

Puis naviguer vers : `http://<ip-robot>:5000/mission-control`

---

## Routes API

| Route | Méthode | Description |
|-------|---------|-------------|
| `/mission-control` | GET | Page principale (HTML) |
| `/api/mc/pose` | GET | Pose courante du robot |
| `/api/mc/path` | GET | Historique trajectoire (`?limit=N`) |
| `/api/mc/status` | GET | Statut de l'adapter SLAM |
| `/api/mc/reset` | POST | Reset du tracking / trajectoire |

### Exemple `/api/mc/pose`
```json
{
  "x": 1.2345,
  "y": -0.8732,
  "theta": 0.5236,
  "source": "mock",
  "timestamp": "2026-05-04T12:00:00+00:00",
  "confidence": 1.0
}
```

### Exemple `/api/mc/status`
```json
{
  "mode": "mock",
  "running": true,
  "lidar_available": false,
  "slam_available": false,
  "history_length": 312,
  "timestamp": "2026-05-04T12:00:00+00:00"
}
```

---

## Modes de positionnement

| Mode | Déclenchement | Description |
|------|--------------|-------------|
| `mock` | Défaut (LiDAR absent) | Trajectoire Lissajous simulée, toujours disponible |
| `lidar_basic` | LiDAR détecté (`base.use_lidar=True`) | Données YDLiDAR brutes + dead-reckoning (placeholder) |
| `slam` | Réservé ROS2 | À brancher via `_read_slam()` dans `slam_adapter.py` |

La détection est automatique — pas besoin de configuration manuelle.

---

## Désactiver le mode mock

Le mode mock s'active automatiquement quand le LiDAR est absent.
Pour le forcer désactivé (position fixe à l'origine) :

Dans `mission_control/slam_adapter.py`, modifier `_mock_pose()` :
```python
def _mock_pose(self) -> RobotPose:
    return RobotPose(x=0, y=0, theta=0, source='mock', confidence=0.0)
```

---

## Brancher le vrai SLAM (ROS2 / Nav2)

### Étape 1 — Recevoir les données ROS2 dans un thread

```python
# Dans ton bridge ROS2 (ex: ros2_bridge.py)
import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped

def amcl_callback(msg):
    from mission_control.slam_adapter import get_adapter
    adapter = get_adapter()
    # Convertir le quaternion ROS2 en angle yaw
    import math
    q = msg.pose.pose.orientation
    yaw = math.atan2(2*(q.w*q.z + q.x*q.y), 1 - 2*(q.y**2 + q.z**2))
    # Mettre à jour le store directement
    from mission_control.state import RobotPose, get_store
    pose = RobotPose(
        x=msg.pose.pose.position.x,
        y=msg.pose.pose.position.y,
        theta=yaw,
        source='slam',
        confidence=1.0 - msg.pose.covariance[0]  # adapter selon ta source
    )
    get_store().update(pose)
```

### Étape 2 — Signaler SLAM disponible

Dans `slam_adapter.py`, modifier `get_slam_status()` :
```python
'slam_available': True,   # changer quand le bridge ROS2 est actif
```

Et `_active_mode()` :
```python
def _active_mode(self) -> str:
    if self._slam_connected:   # ajouter ce flag depuis ton bridge
        return 'slam'
    if self._lidar_available():
        return 'lidar_basic'
    return 'mock'
```

### Étape 3 — Odométrie LiDAR complète

Implémenter la dead-reckoning dans `_read_lidar_basic()` :
- Utiliser les angles/distances YDLiDAR + ICP ou scan matching
- Librairie recommandée : `python-icp` ou `open3d`
- Alternative : brancher Nav2 wheel odometry via `/odom` topic

---

## Stockage futur

L'historique est en mémoire (`TrajectoryStore`, max 2000 points).

Pour persister en JSON ou SQLite, créer un wrapper dans `state.py` :
```python
# JSON export
import json
def export_path_json(path, filepath):
    with open(filepath, 'w') as f:
        json.dump(path, f, indent=2)

# SQLite (ajouter sqlite3 import)
def save_to_sqlite(pose_dict, db_path='mission_log.db'):
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO poses VALUES (?,?,?,?,?,?)",
        (pose_dict['x'], pose_dict['y'], pose_dict['theta'],
         pose_dict['source'], pose_dict['timestamp'], pose_dict['confidence'])
    )
    conn.commit(); conn.close()
```

---

## Interface utilisateur

- **Carte 2D** : canvas HTML5, grille en mètres, origine marquée
- **Robot** : triangle animé pointant dans la direction `theta`
- **Trajectoire** : ligne verte persistante
- **Pan** : drag souris sur la carte
- **Zoom** : molette souris ou boutons +/−
- **Panneau** : x, y, θ, source, confidence, timestamp, statut LiDAR/SLAM
- **Caméra** : flux MJPEG `/video_feed` intégré
- **Reset** : efface l'historique et recentre la carte
- **Thème** : synchronisé avec le thème actif de l'application

---

## Test local sans robot

```bash
# L'app tourne normalement, le mode mock simule la trajectoire
python app.py

# Tester l'API directement
curl http://localhost:5000/api/mc/pose
curl http://localhost:5000/api/mc/status
curl http://localhost:5000/api/mc/path?limit=10
curl -X POST http://localhost:5000/api/mc/reset
```
