"""
A system for handling/understanding BuddyPress notifications
"""

from knowledge_commons_profiles.newprofile.models import WpBpGroup
from knowledge_commons_profiles.newprofile.models import WpBpNotification
from knowledge_commons_profiles.newprofile.models import WpUser


class BuddyPressNotification:
    """
    A class representing a BuddyPress notification
    """

    def __init__(self, notification_item, request=None):
        """
        Constructor
        """
        self.notification_item = notification_item
        self.request = request

    def __str__(self):
        """
        Get a string representation of the notification
        """
        return self.get_string()[0]

    def get_string(self, username="", short=False):  # noqa: PLR0911
        """
        Returns a human-readable string representation of the notification,
        a link to the notification, and whether this is a Django URL
        """

        """
        Possible values:
            comment_reply -- deprecated?: rarely used
            deposit_published -- deprecated: from CORE
            deposit_review -- deprecated: from CORE
            friendship_accepted -- deprecated?: rarely used
            friendship_request -- deprecated?: rarely used
            group_invite -- unsure if used
            join_mla_forum -- unsure if used
            membership_request_accepted -- possibly used
            membership_request_rejected -- possibly (but rarely) used
            member_promoted_to_admin -- possibly used
            member_promoted_to_mod -- possibly (but rarely) used
            newsletter_opt_out -- possibly (but rarely) used
            new_at_mention -- possibly (but rarely) used
            new_follow -- used a lot
            new_group_site_member -- used a lot
            new_membership_request -- used a lot
            new_message -- possibly (but rarely) used
            new_user_email_settings -- used a lot
            update_reply -- possibly (but rarely) used
        """

        from knowledge_commons_profiles.newprofile.api import API

        api_me = API(
            self.request,
            username,
            use_wordpress=True,
            create=False,
        )

        if not api_me:
            return "User not logged in"

        match self.notification_item.component_action:
            case "group_invite":
                # item_id = group ID
                group_id = self.notification_item.item_id
                try:
                    group = WpBpGroup.objects.get(id=group_id)
                except WpBpGroup.DoesNotExist:
                    return "", None, False

                return (
                    f"You have an invitation to the group: {group.name}",
                    f"https://hcommons.org/members/{api_me.wp_user.user_login}"
                    f"/groups/invites/?n=1",
                    False,
                )
            case "new_message":
                # item_id = message ID
                message_id = self.notification_item.item_id
                # secondary_item_id = user
                from_user = WpUser.objects.get(
                    id=self.notification_item.secondary_item_id,
                )

                return (
                    f"New message from {from_user.user_login}",
                    f"https://hcommons.org/members/"
                    f"{api_me.wp_user.user_login}/messages/view/{message_id}/",
                    False,
                )
            case "new_follow":
                if short:
                    # we want to aggregate and count new follows
                    count = WpBpNotification.objects.filter(
                        user_id=self.notification_item.user_id,
                        component_name=self.notification_item.component_name,
                        component_action=self.notification_item.component_action,
                        is_new=True,
                    ).count()

                    return (
                        f"You have {count} new followers",
                        f"https://hcommons.org/members/"
                        f"{api_me.wp_user.user_login}/notifications/",
                        False,
                    )

                # item_id = user
                follow_user = WpUser.objects.get(
                    id=self.notification_item.item_id,
                )

                return (
                    f"{follow_user.display_name} is now following you",
                    ("profile", follow_user.user_login),
                    True,
                )
            case "new_user_email_settings":
                # message shown to new users
                return (
                    "Welcome! Be sure to review your email preferences.",
                    None,
                    False,
                )

        return ""
