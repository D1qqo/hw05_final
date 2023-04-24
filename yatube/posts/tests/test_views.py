from django.test import Client, TestCase
from django.urls import reverse
from django import forms
from ..models import Group, Post, User, Follow
from ..forms import PostForm
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache


class PostPagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='TestUser')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание группы',
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
            text='Тестовый текст поста',
            author=cls.user,
            group=cls.group,
            image=uploaded,
        )

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_urls_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_url_names = {
            reverse('posts:index'):
            'posts/index.html',
            reverse('posts:group_list', args=[self.group.slug]):
            'posts/group_list.html',
            reverse('posts:profile', args=[self.user.username]):
            'posts/profile.html',
            reverse('posts:post_detail', args=[self.post.id]):
            'posts/post_detail.html',
            reverse('posts:create'):
            'posts/create_post.html',
            reverse('posts:edit', args=[self.post.id]):
            'posts/create_post.html',
        }
        for reverse_name, template_name in templates_url_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template_name)

    def function_check(self, response, boolean=False):
        """Функция проверки"""
        if boolean:
            post = response.context.get('post')
        else:
            post = response.context['page_obj'][0]
        self.assertEqual(post.text, self.post.text)
        self.assertEqual(post.author, self.user)
        self.assertEqual(post.group, self.group)
        self.assertEqual(post.pub_date, self.post.pub_date)

    def test_index_pages_show_correct_context(self):
        """Проверка контекста в index"""
        response = self.authorized_client.get(reverse('posts:index'))
        self.function_check(response)

    def test_group_list_pages_show_correct_context(self):
        """Проверка контекста в group_list"""
        response = self.authorized_client.get(reverse(
            'posts:group_list', args=(self.group.slug,))
        )
        self.function_check(response)
        group_context = response.context['group']
        self.assertEqual(group_context, self.group)

    def test_profile_pages_show_correct_context(self):
        """Проверка контекста в profile"""
        response = self.authorized_client.get(reverse(
            'posts:profile', args=(self.user.username,))
        )
        self.function_check(response)
        group_context = response.context['author']
        self.assertEqual(group_context, self.user)

    def test_post_detail_pages_show_correct_context(self):
        """Проверка контекста в post_detail"""
        response = self.authorized_client.get(reverse(
            'posts:post_detail', args=(self.post.id,))
        )
        self.function_check(response, True)

    def test_post_create_and_edit_show_correct_context(self):
        """Шаблон create_post (create) и (edit) сформирован
        с правильным контекстом."""
        context_urls = (
            ('posts:create', None),
            ('posts:edit', (self.post.id,))
        )
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
            'image': forms.fields.ImageField,
        }
        for address, args in context_urls:
            with self.subTest(address=address):
                response = self.authorized_client.get(
                    reverse(address, args=args)
                )
                self.assertIn('form', response.context)
                self.assertIsInstance(response.context.get('form'), PostForm)
                for value, expected in form_fields.items():
                    with self.subTest(value=value):
                        form_field = response.context.get('form').fields.get(
                            value
                        )
                        self.assertIsInstance(form_field, expected)

    def test_create_post(self):
        """Дополнительная проверка при создании поста."""
        pages = (
            reverse("posts:index"),
            reverse("posts:group_list", kwargs={'slug': 'test-slug'}),
            reverse("posts:profile", kwargs={'username': 'TestUser'})
        )
        for page in pages:
            response = self.authorized_client.get(page)
            post = response.context['page_obj'][0]
            self.check_card_of_post(post)

    def check_card_of_post(self, post):
        self.assertEqual(post.text, self.post.text)
        self.assertEqual(post.author.username, self.user.username)
        self.assertEqual(post.group.id, self.group.id)
        self.assertEqual(post.image, self.post.image)

    def test_index_page_cache(self):
        """Проверка кеширования index page"""
        first_response = self.authorized_client.get(reverse('posts:index'))
        Post.objects.all().delete()
        second_response = self.authorized_client.get(reverse('posts:index'))
        self.assertEqual(first_response.content, second_response.content)
        cache.clear()
        page_cleared = self.authorized_client.get(reverse('posts:index'))
        self.assertNotEqual(
            first_response,
            page_cleared
        )


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание группы'
        )
        posts = [
            Post(
                author=cls.user,
                text='Тестовый текст поста {i}',
                group=cls.group
            )
            for i in range(1, 14)
        ]
        Post.objects.bulk_create(objs=posts)

    def setUp(self):
        self.guest_client = Client()
        self.author = Client()
        self.author.force_login(self.user)

    def test_first_page_contains_ten_records(self):
        """Проверка, на первой странице должно быть 10 постов"""
        response = self.author.get(reverse('posts:index'))
        self.assertEqual(len(response.context['page_obj']), 10)

    def test_second_page_contains_three_records(self):
        """Проверка, на второй странице должно быть 3 поста"""
        response = self.author.get(reverse('posts:index') + '?page=2')
        self.assertEqual(len(response.context['page_obj']), 3)


class FollowTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.following = User.objects.create_user(username='author')
        cls.follower = User.objects.create_user(username='subscriber')

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.follower)
        cache.clear()

    def test_follow_create(self):
        """Авторизованный пользователь может подписываться
        на других пользователей."""
        self.authorized_client.get(
            reverse('posts:profile_follow',
                    kwargs={'username': self.following.username})
        )
        self.assertTrue(
            Follow.objects.filter(user=self.follower,
                                  author=self.following).exists()
        )

    def test_follow_delete(self):
        """Авторизованный пользователь может отписываться
        от других пользователей."""
        Follow.objects.create(user=self.follower, author=self.following)
        self.authorized_client.get(
            reverse('posts:profile_unfollow',
                    kwargs={'username': self.following.username})
        )
        self.assertFalse(
            Follow.objects.filter(user=self.follower,
                                  author=self.following).exists()
        )

    def test_check_posts_in_follow_index(self):
        """Посты избранных авторов выводятся в follow_index."""
        post = Post.objects.create(
            text='тестовый текст поста для проверки follow_index',
            author=self.following
        )
        Follow.objects.create(
            user=self.follower,
            author=self.following
        )
        response = self.authorized_client.get(reverse('posts:follow_index'))
        self.assertIn(post, response.context['page_obj'])

    def test_check_posts_not_in_follow(self):
        """Посты не избранных авторов не выводятся в follow_index."""
        post = Post.objects.create(
            text='тестовый текст поста для проверки follow_index',
            author=self.following
        )
        response = self.authorized_client.get(
            reverse('posts:follow_index'))
        self.assertNotIn(post, response.context['page_obj'])
