Fitbit Social Data Export

Fitbit Social Data Export provides a way to export your social connections and interactions on Fitbit.
The data is exported in CSV format.

Files Included:
----------

friends.csv - The CSV file containing your list of friends.

This file contains the following columns:
  created_at                      - The time when you became friends.
  display_name                    - The display name of your friend.

incoming_invitations.csv - The CSV file containing your incoming friend requests.

This file contains the following columns:
  type                            - The type of friend request (e.g., FRIEND).
  direction                       - The direction of the friend request (e.g., INCOMING).
  created_at                      - The time when the friend request was created.
  friend_display_name             - The display name of the user who sent the friend request.

permissions.csv - The CSV file containing your permission settings.

This file contains the following columns:
  reader_type                     - The type of user who has access to your data (e.g. ALL_FRIENDS).
  data_type                       - The type of data that is shared with the user (e.g., steps, heart_rate).
  state                           - The state of the permission (e.g., GRANTED, REVOKED).

blocks.csv - The CSV file containing your list of blocked users.

This file contains the following columns:
  created_at                      - The time when the block was created.
  email                           - The email address of the blocked user.
