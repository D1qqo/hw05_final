from http import HTTPStatus
from django.test import Client, TestCase
from ..models import Group, Post, User


class StaticURLTests(TestCase):
    def setUp(self):
        self.guest_client = Client()

    def test_homepage(self):
        response = self.guest_client.get('/')
        self.assertEqual(response.status_code, HTTPStatus.OK)


class PostURLTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.guest_client = Client()
        cls.user = User.objects.create_user(username='TestUser')
        cls.authorized_client = Client()
        cls.authorized_client.force_login(cls.user)

        cls.group = Group.objects.create(
            title='Тестовая группа',
            description='Тестовое описание группы',
            slug='test-slug',
        )

        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый текст поста',
        )

    def test_urls_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_url_names = {
            'posts/index.html': '/',
            'posts/create_post.html': '/create/',
            'posts/group_list.html': f'/group/{self.group.slug}/',
            'posts/post_detail.html': f'/posts/{self.post.id}/',
            'posts/profile.html': f'/profile/{self.user.username}/',
        }
        for template, address in templates_url_names.items():
            with self.subTest(address=address):
                response = self.authorized_client.get(address)
                self.assertTemplateUsed(response, template)

    def test_page_accessible_any_users(self):
        """Страница, которые доступны любому пользователю."""

        test_items = {
            '/': '/',
            '/group/slug/': f'/group/{self.group.slug}/',
            '/posts/id/': f'/posts/{self.post.id}/',
            '/profile/username/': f'/profile/{self.user.username}/'
        }

        for path, expected_value in test_items.items():
            with self.subTest(path=path):
                self.assertEqual(
                    self.guest_client.get(expected_value).status_code,
                    HTTPStatus.OK)

    def test_page_accessible_authorized_users(self):
        """Страница доступна авторизованному пользователю."""
        test_items = {
            '/posts/id/edit/': f'/posts/{self.post.id}/edit/',
            '/create/': '/create/',
        }

        for path, expected_value in test_items.items():
            with self.subTest(path=path):
                self.assertEqual(
                    self.authorized_client.get(expected_value)
                    .status_code, HTTPStatus.OK)

    def test_unexisting_page(self):
        """Страница  доступна любому пользователю."""
        response = self.guest_client.get('/unexisting_page/')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_create_url_redirect_unauthorized_on_auth_login(self):
        """Страница по адресу /create/ перенаправит анонимного
        пользователя на страницу логина.
        """
        response = self.guest_client.get('/create/', follow=True)
        self.assertRedirects(
            response, '/auth/login/?next=/create/'
        )

    def test_posts_id_edit_url_redirect_unathorized_on_auth_login(self):
        """Страница по адресу /edit/ перенаправит анонимного
        пользователя на страницу логина.
        """
        response = self.guest_client.get(
            f'/posts/{self.post.id}/edit/', follow=True
        )
        self.assertRedirects(
            response, f'/auth/login/?next=/posts/{self.post.id}/edit/'
        )

    def test_posts_id_comment_url_redirect_unathorized_on_auth_login(self):
        """Страница по адресу /comment/ перенаправит анонимного
        пользователя на страницу логина.
        """
        response = self.guest_client.get(
            f'/posts/{self.post.id}/comment/', follow=True
        )
        self.assertRedirects(
            response, f'/auth/login/?next=/posts/{self.post.id}/comment/'
        )
