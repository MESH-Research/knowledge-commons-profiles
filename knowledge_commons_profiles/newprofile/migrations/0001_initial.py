# Generated by Django 5.1.4 on 2025-01-22 19:18

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AcademicInterest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("text", models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name="Profile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("username", models.CharField(db_index=True, max_length=255)),
                (
                    "central_user_id",
                    models.IntegerField(db_index=True, null=True),
                ),
                ("affiliation", models.CharField(max_length=255)),
                ("twitter", models.CharField(blank=True, max_length=255)),
                ("github", models.CharField(blank=True, max_length=255)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("orcid", models.CharField(blank=True, max_length=255)),
                ("mastodon", models.CharField(blank=True, max_length=255)),
                ("profile_image", models.URLField(blank=True)),
                (
                    "works_username",
                    models.CharField(blank=True, max_length=255),
                ),
                ("about_user", models.TextField(blank=True, null=True)),
                ("education", models.TextField(blank=True, null=True)),
                ("upcoming_talks", models.TextField(blank=True, null=True)),
                ("projects", models.TextField(blank=True, null=True)),
                ("publications", models.TextField(blank=True, null=True)),
                ("site", models.TextField(blank=True, null=True)),
                (
                    "institutional_or_other_affiliation",
                    models.TextField(blank=True, null=True),
                ),
                ("title", models.TextField(blank=True, null=True)),
                ("figshare_url", models.TextField(blank=True, null=True)),
                ("commons_groups", models.TextField(blank=True, null=True)),
                (
                    "recent_commons_activity",
                    models.TextField(blank=True, null=True),
                ),
                ("commons_sites", models.TextField(blank=True, null=True)),
                ("blog_posts", models.TextField(blank=True, null=True)),
                ("cv", models.TextField(blank=True, null=True)),
                ("facebook", models.TextField(blank=True, null=True)),
                ("linkedin", models.TextField(blank=True, null=True)),
                ("website", models.TextField(blank=True, null=True)),
                (
                    "academic_interests",
                    models.ManyToManyField(
                        related_name="profiles",
                        to="newprofile.academicinterest",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="WpBlog",
            fields=[
                (
                    "blog_id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                ("site_id", models.BigIntegerField(default=0)),
                ("domain", models.CharField(default="", max_length=200)),
                ("path", models.CharField(default="", max_length=100)),
                (
                    "registered",
                    models.DateTimeField(default="0000-00-00 00:00:00"),
                ),
                (
                    "last_updated",
                    models.DateTimeField(default="0000-00-00 00:00:00"),
                ),
                ("public", models.SmallIntegerField(default=1)),
                ("archived", models.SmallIntegerField(default=0)),
                ("mature", models.SmallIntegerField(default=0)),
                ("spam", models.SmallIntegerField(default=0)),
                ("deleted", models.SmallIntegerField(default=0)),
                ("lang_id", models.IntegerField(db_index=True, default=0)),
            ],
            options={
                "db_table": "wp_blogs",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WpBpActivity",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("component", models.CharField(max_length=75)),
                ("type", models.CharField(max_length=75)),
                ("action", models.TextField()),
                ("content", models.TextField()),
                ("primary_link", models.TextField()),
                ("item_id", models.BigIntegerField()),
                ("secondary_item_id", models.BigIntegerField(null=True)),
                ("date_recorded", models.DateTimeField()),
                ("hide_sitewide", models.BooleanField(default=False)),
                ("mptt_left", models.IntegerField(default=0)),
                ("mptt_right", models.IntegerField(default=0)),
                ("is_spam", models.BooleanField(default=False)),
            ],
            options={
                "db_table": "wp_bp_activity",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WpBpActivityMeta",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("meta_key", models.CharField(max_length=255, null=True)),
                ("meta_value", models.TextField(null=True)),
            ],
            options={
                "db_table": "wp_bp_activity_meta",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WpBpFollow",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("follow_type", models.CharField(max_length=75)),
                ("date_recorded", models.DateTimeField()),
            ],
            options={
                "db_table": "wp_bp_follow",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WpBpGroup",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("slug", models.CharField(max_length=200)),
                ("description", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("public", "Public"),
                            ("private", "Private"),
                            ("hidden", "Hidden"),
                        ],
                        db_index=True,
                        default="public",
                        max_length=10,
                    ),
                ),
                ("enable_forum", models.BooleanField(default=True)),
                ("date_created", models.DateTimeField()),
                (
                    "parent_id",
                    models.BigIntegerField(db_index=True, default=0),
                ),
            ],
            options={
                "db_table": "wp_bp_groups",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WpBpGroupMember",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("inviter_id", models.BigIntegerField(db_index=True)),
                (
                    "is_admin",
                    models.BooleanField(db_index=True, default=False),
                ),
                ("is_mod", models.BooleanField(db_index=True, default=False)),
                ("user_title", models.CharField(max_length=100)),
                ("date_modified", models.DateTimeField()),
                ("comments", models.TextField()),
                (
                    "is_confirmed",
                    models.BooleanField(db_index=True, default=False),
                ),
                ("is_banned", models.BooleanField(default=False)),
                ("invite_sent", models.BooleanField(default=False)),
            ],
            options={
                "db_table": "wp_bp_groups_members",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WpBpNotification",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("item_id", models.BigIntegerField()),
                ("secondary_item_id", models.BigIntegerField(null=True)),
                ("component_name", models.CharField(max_length=75)),
                ("component_action", models.CharField(max_length=75)),
                ("date_notified", models.DateTimeField()),
                ("is_new", models.BooleanField(default=False)),
            ],
            options={
                "db_table": "wp_bp_notifications",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WpBpUserBlogMeta",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("meta_key", models.CharField(max_length=255, null=True)),
                ("meta_value", models.TextField(null=True)),
            ],
            options={
                "db_table": "wp_bp_user_blogs_blogmeta",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WpPost",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        db_column="ID", primary_key=True, serialize=False
                    ),
                ),
                (
                    "post_date",
                    models.DateTimeField(default="0000-00-00 00:00:00"),
                ),
                (
                    "post_date_gmt",
                    models.DateTimeField(default="0000-00-00 00:00:00"),
                ),
                ("post_content", models.TextField()),
                ("post_title", models.TextField()),
                ("post_excerpt", models.TextField()),
                (
                    "post_status",
                    models.CharField(default="publish", max_length=20),
                ),
                (
                    "comment_status",
                    models.CharField(default="open", max_length=20),
                ),
                (
                    "ping_status",
                    models.CharField(default="open", max_length=20),
                ),
                (
                    "post_password",
                    models.CharField(default="", max_length=255),
                ),
                (
                    "post_name",
                    models.CharField(
                        db_index=True, default="", max_length=200
                    ),
                ),
                ("to_ping", models.TextField()),
                ("pinged", models.TextField()),
                (
                    "post_modified",
                    models.DateTimeField(default="0000-00-00 00:00:00"),
                ),
                (
                    "post_modified_gmt",
                    models.DateTimeField(default="0000-00-00 00:00:00"),
                ),
                ("post_content_filtered", models.TextField()),
                (
                    "post_parent",
                    models.BigIntegerField(db_index=True, default=0),
                ),
                ("guid", models.CharField(default="", max_length=255)),
                ("menu_order", models.IntegerField(default=0)),
                ("post_type", models.CharField(default="post", max_length=20)),
                (
                    "post_mime_type",
                    models.CharField(default="", max_length=100),
                ),
                ("comment_count", models.BigIntegerField(default=0)),
                (
                    "user_voice_username",
                    models.CharField(
                        db_column="user-voice_username",
                        default="",
                        max_length=128,
                    ),
                ),
                (
                    "user_voice_slug",
                    models.CharField(
                        db_column="user-voice_slug",
                        default="general",
                        max_length=128,
                    ),
                ),
                (
                    "user_voice_active",
                    models.BooleanField(
                        db_column="user-voice_active", default=False
                    ),
                ),
                (
                    "user_voice_alignment",
                    models.CharField(
                        choices=[("left", "Left"), ("right", "Right")],
                        db_column="user-voice_alignment",
                        default="right",
                        max_length=5,
                    ),
                ),
                (
                    "user_voice_color",
                    models.CharField(
                        db_column="user-voice_color",
                        default="00BCBA",
                        max_length=6,
                    ),
                ),
            ],
            options={
                "db_table": "wp_posts",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WpPostSubTable",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        db_column="ID", primary_key=True, serialize=False
                    ),
                ),
                ("blogname", models.CharField(default="", max_length=255)),
                ("blogdomain", models.CharField(default="", max_length=255)),
                ("blogpath", models.CharField(default="", max_length=255)),
                (
                    "post_date",
                    models.DateTimeField(default="0000-00-00 00:00:00"),
                ),
                (
                    "post_date_gmt",
                    models.DateTimeField(default="0000-00-00 00:00:00"),
                ),
                ("post_content", models.TextField()),
                ("post_title", models.TextField()),
                ("post_excerpt", models.TextField()),
                (
                    "post_status",
                    models.CharField(default="publish", max_length=20),
                ),
                (
                    "comment_status",
                    models.CharField(default="open", max_length=20),
                ),
                (
                    "ping_status",
                    models.CharField(default="open", max_length=20),
                ),
                (
                    "post_password",
                    models.CharField(default="", max_length=255),
                ),
                (
                    "post_name",
                    models.CharField(
                        db_index=True, default="", max_length=200
                    ),
                ),
                ("to_ping", models.TextField()),
                ("pinged", models.TextField()),
                (
                    "post_modified",
                    models.DateTimeField(default="0000-00-00 00:00:00"),
                ),
                (
                    "post_modified_gmt",
                    models.DateTimeField(default="0000-00-00 00:00:00"),
                ),
                ("post_content_filtered", models.TextField()),
                (
                    "post_parent",
                    models.BigIntegerField(db_index=True, default=0),
                ),
                ("guid", models.CharField(default="", max_length=255)),
                ("menu_order", models.IntegerField(default=0)),
                ("post_type", models.CharField(default="post", max_length=20)),
                (
                    "post_mime_type",
                    models.CharField(default="", max_length=100),
                ),
                ("comment_count", models.BigIntegerField(default=0)),
                (
                    "user_voice_username",
                    models.CharField(
                        db_column="user-voice_username",
                        default="",
                        max_length=128,
                    ),
                ),
                (
                    "user_voice_slug",
                    models.CharField(
                        db_column="user-voice_slug",
                        default="general",
                        max_length=128,
                    ),
                ),
                (
                    "user_voice_active",
                    models.BooleanField(
                        db_column="user-voice_active", default=False
                    ),
                ),
                (
                    "user_voice_alignment",
                    models.CharField(
                        choices=[("left", "Left"), ("right", "Right")],
                        db_column="user-voice_alignment",
                        default="right",
                        max_length=5,
                    ),
                ),
                (
                    "user_voice_color",
                    models.CharField(
                        db_column="user-voice_color",
                        default="00BCBA",
                        max_length=6,
                    ),
                ),
            ],
            options={
                "db_table": "wp_posts",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WpProfileData",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("value", models.TextField()),
                ("last_updated", models.DateTimeField()),
            ],
            options={
                "db_table": "wp_bp_xprofile_data",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WpProfileFields",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("group_id", models.BigIntegerField(db_index=True)),
                ("parent_id", models.BigIntegerField(db_index=True)),
                ("type", models.CharField(max_length=150)),
                ("name", models.CharField(max_length=150)),
                ("description", models.TextField()),
                (
                    "is_required",
                    models.BooleanField(db_index=True, default=False),
                ),
                ("is_default_option", models.BooleanField(default=False)),
                (
                    "field_order",
                    models.BigIntegerField(db_index=True, default=0),
                ),
                ("option_order", models.BigIntegerField(default=0)),
                ("order_by", models.CharField(default="", max_length=15)),
                (
                    "can_delete",
                    models.BooleanField(db_index=True, default=True),
                ),
            ],
            options={
                "db_table": "wp_bp_xprofile_fields",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WpTermRelationships",
            fields=[
                (
                    "object_id",
                    models.BigIntegerField(primary_key=True, serialize=False),
                ),
                ("term_order", models.IntegerField(default=0)),
            ],
            options={
                "db_table": "wp_term_relationships",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WpTermTaxonomy",
            fields=[
                (
                    "term_taxonomy_id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                ("term_id", models.BigIntegerField()),
                ("taxonomy", models.CharField(max_length=32)),
                ("description", models.TextField()),
                ("parent", models.BigIntegerField(default=0)),
                ("count", models.BigIntegerField(default=0)),
            ],
            options={
                "db_table": "wp_term_taxonomy",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WpUser",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        db_column="ID", primary_key=True, serialize=False
                    ),
                ),
                (
                    "user_login",
                    models.CharField(default="", max_length=60, unique=True),
                ),
                ("user_pass", models.CharField(default="", max_length=255)),
                (
                    "user_nicename",
                    models.CharField(db_index=True, default="", max_length=50),
                ),
                (
                    "user_email",
                    models.CharField(
                        db_index=True, default="", max_length=100
                    ),
                ),
                ("user_url", models.CharField(default="", max_length=100)),
                (
                    "user_registered",
                    models.DateTimeField(
                        db_index=True, default="0000-00-00 00:00:00"
                    ),
                ),
                (
                    "user_activation_key",
                    models.CharField(default="", max_length=255),
                ),
                ("user_status", models.IntegerField(default=0)),
                ("display_name", models.CharField(default="", max_length=250)),
                ("spam", models.SmallIntegerField(default=0)),
                ("deleted", models.SmallIntegerField(default=0)),
            ],
            options={
                "db_table": "wp_users",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WpUserMeta",
            fields=[
                (
                    "umeta_id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                (
                    "meta_key",
                    models.CharField(db_index=True, max_length=255, null=True),
                ),
                ("meta_value", models.TextField(null=True)),
            ],
            options={
                "db_table": "wp_usermeta",
                "managed": False,
            },
        ),
    ]
