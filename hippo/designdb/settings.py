DEFAULT_POSE_METHODS: list[str] = ['xray']

# The tag vocabulary is maintained outside HIPPO; ingestion never creates tags.
# The add_tag debugging helpers still may, guarded by this flag. Set False in
# production to make the vocabulary strictly external.
ALLOW_TAG_CREATION: bool = True
