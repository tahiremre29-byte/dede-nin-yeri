from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import orient
import mapbox_earcut
import numpy as np

def extrude_polygon(poly, thickness):
    """
    Ensures solid 3D manifold by normalizing winding order and cap normals.
    Supports Polygon and MultiPolygon.
    """
    if isinstance(poly, MultiPolygon):
        all_v, all_f, v_off = [], [], 0
        for g in poly.geoms:
            v, f = extrude_polygon(g, thickness)
            all_v.append(v); all_f.append(f + v_off); v_off += len(v)
        return np.vstack(all_v), np.vstack(all_f)

    # 1. Normalize orientation (Counter-Clockwise)
    poly = orient(poly, sign=1.0)
    
    # Coordinates for earcut
    ext_coords = np.array(poly.exterior.coords)[:-1]
    all_coords = [ext_coords]
    ring_ends = [len(ext_coords)]
    curr_len = len(ext_coords)
    
    for interior in poly.interiors:
        int_coords = np.array(interior.coords)[:-1]
        curr_len += len(int_coords)
        ring_ends.append(curr_len)
        all_coords.append(int_coords)
        
    pts_2d = np.vstack(all_coords)
    num_pts = len(pts_2d)
    
    # Vertices
    vertices = np.zeros((num_pts * 2, 3))
    vertices[:num_pts, :2] = pts_2d
    vertices[:num_pts, 2] = 0
    vertices[num_pts:, :2] = pts_2d
    vertices[num_pts:, 2] = thickness
    
    # Triangulate
    tri_indices = mapbox_earcut.triangulate_float64(pts_2d, np.array(ring_ends, dtype=np.uint32)).reshape(-1, 3)
    
    faces = []
    # 2. Bottom Cap (Facing AWAY from +Z -> Must be Clockwise in XY to be outward)
    for t in tri_indices:
        faces.append([t[0], t[2], t[1]]) # Flip CCW to CW
    # 3. Top Cap (Facing TOWARD +Z -> Must be Counter-Clockwise in XY to be outward)
    for t in tri_indices:
        faces.append([t[0] + num_pts, t[1] + num_pts, t[2] + num_pts]) # CCW
        
    # 4. Side Faces
    rings = [ext_coords] + [np.array(i.coords)[:-1] for i in poly.interiors]
    offset = 0
    for ring in rings:
        n = len(ring)
        for i in range(n):
            next_i = (i + 1) % n
            v1_b, v2_b = offset + i, offset + next_i
            v1_t, v2_t = v1_b + num_pts, v2_b + num_pts
            
            # Outward Normal for CCW ring: [Bottom1, Bottom2, Top1] and [Bottom2, Top2, Top1]
            faces.append([v1_b, v2_b, v1_t])
            faces.append([v2_b, v2_t, v1_t])
        offset += n
        
    return vertices, np.array(faces)

def transform_vertices(vertices, rotation_angles, translation):
    rx, ry, rz = np.radians(rotation_angles)
    Rx = np.array([[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]])
    Ry = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
    Rz = np.array([[np.cos(rz), -np.sin(rz), 0], [np.sin(rz), np.cos(rz), 0], [0, 0, 1]])
    R = Rz @ Ry @ Rx
    return (vertices @ R.T) + np.array(translation)

def save_3d_assembly(panel_data, output_path, scale=0.1):
    """
    panel_data: list of dicts { 'poly': poly, 't': t, 'rot': (r), 'pos': (p) }
    scale: factor to convert units (default 0.1 for mm to cm)
    """
    all_vertices = []
    all_faces = []
    vertex_offset = 0
    
    for p in panel_data:
        v, f = extrude_polygon(p['poly'], p['t'])
        v_transformed = transform_vertices(v, p['rot'], p['pos'])
        
        # Apply Global Scale
        v_scaled = v_transformed * scale
        
        all_vertices.append(v_scaled)
        all_faces.append(f + vertex_offset)
        vertex_offset += len(v_scaled)
        
    final_vertices = np.vstack(all_vertices)
    final_faces = np.vstack(all_faces)
    
    # Auto-Centering (Double check)
    v_min = np.min(final_vertices, axis=0)
    v_max = np.max(final_vertices, axis=0)
    center = (v_min + v_max) / 2.0
    final_vertices -= center
    
    try:
        from stl import mesh
        box_mesh = mesh.Mesh(np.zeros(final_faces.shape[0], dtype=mesh.Mesh.dtype))
        for i, f in enumerate(final_faces):
            for j in range(3):
                box_mesh.vectors[i][j] = final_vertices[f[j], :]
        box_mesh.save(output_path)
    except Exception as e:
        print(f"Error saving STL: {e}")
        
    return output_path
