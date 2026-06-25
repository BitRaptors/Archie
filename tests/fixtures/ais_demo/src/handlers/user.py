def get_user(user_repo, user_id):
    # Conforms: goes through the repository layer.
    return user_repo.get(user_id)
