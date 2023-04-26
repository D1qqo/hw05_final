from django.test import Client, TestCase, override_settings
from django.urls import reverse
from ..models import Post, Group, User, Comment
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
import tempfile
import shutil


TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostFormTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='TestUser')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание группы'
        )
        cls.group1 = Group.objects.create(
            title='Тестовая группа2',
            slug='test-slug2',
            description='Тестовое описание группы2'
        )
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small_2.gif',
            content=small_gif,
            content_type='image/gif',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый текст поста',
            group=cls.group,
            image=uploaded,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_create_post(self):
        """При отправке валидной формы создается запись в Post."""
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый текст поста',
            'group': self.group.id,
            'image': self.post.image,
        }
        response = self.authorized_client.post(
            reverse("posts:create"), data=form_data, follow=True
        )
        self.assertRedirects(
            response, reverse("posts:profile", kwargs={"username": self.user})
        )
        self.assertEqual(Post.objects.count(), posts_count + 1)
        self.assertEqual(Post.objects.first().text, form_data['text'])
        self.assertEqual(Post.objects.first().group, self.group)
        self.assertEqual(Post.objects.first().image, self.post.image)

    def test_post_edit(self):
        """При отправке валидной формы изменяется запись в Post."""
        posts_count = Post.objects.count()
        form_data = {
            "text": "Изменяем текст",
            "group": self.group1.id,
        }
        response = self.authorized_client.post(
            reverse("posts:edit", kwargs=({"post_id": self.post.id})),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(
            response, reverse(
                "posts:post_detail", kwargs={"post_id": self.post.id}
            )
        )
        self.assertEqual(Post.objects.count(), posts_count)
        self.assertTrue(
            Post.objects.filter(
                group=self.group1.id,
                text='Изменяем текст').exists())

    def test_guest_cannot_edit_post(self):
        """
        При отправке валидной формы не изменяется запись в Post,
        если пользователь не авторизован
        """
        posts_count = Post.objects.count()
        form_data = {
            "text": "Тестовый пост",
            "group": self.group.id,
            'image': self.post.image,
        }
        response = self.guest_client.post(
            reverse("posts:edit", kwargs=({"post_id": self.post.id})),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(
            response, f"/auth/login/?next=/posts/{self.post.id}/edit/"
        )
        self.assertEqual(Post.objects.count(), posts_count)

    def test_guest_cannot_create(self):
        """
        При отправке валидной формы не создаётся запись в Post,
        если пользователь не авторизован
        """
        posts_count = Post.objects.count()
        form_data = {
            "text": "Тестовый пост",
            "group": self.group.id,
            'image': self.post.image,
        }
        response = self.guest_client.post(
            reverse("posts:create"),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(
            response, "/auth/login/?next=/create/"
        )
        self.assertEqual(Post.objects.count(), posts_count)


class CommentFormsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author = User.objects.create_user(username='TestUser')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
        )
        cls.post = Post.objects.create(
            author=cls.author,
            text='Тестовый текст поста',
            group=cls.group,
        )

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.author)

    def test_auth_user_can_write_comment(self):
        """Комментарии могут оставлять авторизованные пользователи"""
        comments_count = self.post.comments.count()
        form_data = {
            'text': 'Новый комментарий',
        }
        self.authorized_client.post(
            reverse('posts:add_comment', args=(self.post.id,)),
            data=form_data,
            follow=True,
        )
        self.assertEqual(Post.objects.count(), comments_count + 1)
        self.assertTrue(
            self.post.comments.filter(
                text='Новый комментарий',
                author=self.author
            ).exists()
        )
        comment = Comment.objects.first()
        self.assertEqual(comment.post, self.post)
        self.assertEqual(comment.author, self.author)
        self.assertEqual(comment.text, form_data['text'])

    def test_guest_cannot_write_comment(self):
        """Гости не могут оставлять комментарии"""
        comments_count = self.post.comments.count()
        form_data = {
            'text': 'Новый комментарий',
        }
        self.client.post(
            reverse('posts:add_comment', args=(self.post.id,)),
            data=form_data,
            follow=True,
        )
        self.assertEqual(self.post.comments.count(), comments_count)
