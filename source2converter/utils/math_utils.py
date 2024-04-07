import numpy as np


def rotation_matrix_to_quaternion(rot_mat):
    """
    Method to convert a rotation matrix to a quaternion
    Assumes `rot_mat` is a proper rotation matrix
    """
    qw = np.sqrt(1 + rot_mat[0, 0] + rot_mat[1, 1] + rot_mat[2, 2]) / 2
    qx = (rot_mat[2, 1] - rot_mat[1, 2]) / (4 * qw)
    qy = (rot_mat[0, 2] - rot_mat[2, 0]) / (4 * qw)
    qz = (rot_mat[1, 0] - rot_mat[0, 1]) / (4 * qw)
    return np.array([qw, qx, qy, qz])


def decompose_matrix_to_rts(mat):
    # Ensure the matrix is a numpy array
    mat = np.array(mat)

    # Translation is the last column of the first three rows
    translation = mat[:3, 3]

    # Scale is computed from the columns of the rotation-scale submatrix
    scale = np.linalg.norm(mat[:3, :3], axis=0)

    # Prevent division by zero in case of zero scale
    scale_with_no_zeros = np.where(scale == 0, 1, scale)

    # Rotation matrix is the rotation-scale matrix normalized by scale
    rotation_matrix = mat[:3, :3] / scale_with_no_zeros

    # Convert rotation matrix to quaternion
    quaternion = rotation_matrix_to_quaternion(rotation_matrix)

    return quaternion, translation, scale


def quaternion_to_euler(q):
    # Extract the quaternion components
    w, x, y, z = q

    # Pre-compute repeated values for efficiency
    t0 = +2.0 * (w * x + y * z)
    t1 = +1.0 - 2.0 * (x * x + y * y)
    roll_x = np.arctan2(t0, t1)

    t2 = +2.0 * (w * y - z * x)
    t2 = np.where(t2 > +1.0, +1.0, t2)  # Clamp to avoid NaN in arctan2
    t2 = np.where(t2 < -1.0, -1.0, t2)
    pitch_y = np.arcsin(t2)

    t3 = +2.0 * (w * z + x * y)
    t4 = +1.0 - 2.0 * (y * y + z * z)
    yaw_z = np.arctan2(t3, t4)

    return yaw_z, pitch_y, roll_x  # Return in ZYX order
