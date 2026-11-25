from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .forms import CommentForm, PostForm, ProfileForm
from .models import Category, Post, User

POSTS_PER_PAGE = 10


def posts_with_details():
    return Post.objects.select_related('author', 'category', 'location')


def public_posts_filter():
    return Q(
        is_published=True,
        pub_date__lte=timezone.now(),
        category__is_published=True,
    )


def paginate_posts(request, posts):
    posts = posts.annotate(comment_count=Count('comments')).order_by(
        '-pub_date', '-pk'
    )
    return Paginator(posts, POSTS_PER_PAGE).get_page(request.GET.get('page'))


def get_visible_post(request, post_id):
    visibility = public_posts_filter()
    if request.user.is_authenticated:
        visibility |= Q(author=request.user)
    return get_object_or_404(posts_with_details(), visibility, pk=post_id)


def index(request):
    posts = posts_with_details().filter(public_posts_filter())
    return render(
        request, 'blog/index.html',
        {'page_obj': paginate_posts(request, posts)},
    )


def category_posts(request, category_slug):
    category = get_object_or_404(
        Category, slug=category_slug, is_published=True
    )
    posts = posts_with_details().filter(
        public_posts_filter(), category=category
    )
    return render(
        request, 'blog/category.html',
        {'category': category, 'page_obj': paginate_posts(request, posts)},
    )


def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    posts = posts_with_details().filter(author=profile_user)
    if request.user != profile_user:
        posts = posts.filter(public_posts_filter())
    return render(
        request, 'blog/profile.html',
        {'profile': profile_user, 'page_obj': paginate_posts(request, posts)},
    )


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def edit_profile(request):
    form = ProfileForm(
        request.POST if request.method == 'POST' else None,
        instance=get_object_or_404(User, pk=request.user.pk),
    )
    if form.is_valid():
        profile_user = form.save(commit=False)
        profile_user.save(update_fields=form.fields)
        return redirect('blog:profile', username=profile_user.username)
    return render(request, 'blog/user.html', {'form': form})


def render_post_detail(request, post, form):
    return render(
        request, 'blog/detail.html',
        {
            'post': post,
            'form': form,
            'comments': post.comments.select_related('author'),
        },
    )


def post_detail(request, post_id):
    return render_post_detail(
        request, get_visible_post(request, post_id), CommentForm()
    )


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def create_post(request):
    form = PostForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
    )
    if form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        return redirect('blog:profile', username=request.user.username)
    return render(request, 'blog/create.html', {'form': form})


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def edit_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.author_id != request.user.pk:
        return redirect('blog:post_detail', post_id=post_id)
    form = PostForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
        instance=post,
    )
    if form.is_valid():
        post = form.save(commit=False)
        post.save(update_fields=form.fields)
        return redirect('blog:post_detail', post_id=post_id)
    return render(request, 'blog/create.html', {'form': form})


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def delete_post(request, post_id):
    post = get_object_or_404(posts_with_details(), pk=post_id)
    if post.author_id != request.user.pk:
        return redirect('blog:post_detail', post_id=post_id)
    if request.method == 'POST':
        post.delete()
        return redirect('blog:profile', username=request.user.username)
    return render(
        request, 'blog/create.html', {'form': PostForm(instance=post)}
    )


@login_required
@require_POST
def add_comment(request, post_id):
    post = get_visible_post(request, post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
        return redirect('blog:post_detail', post_id=post_id)
    return render_post_detail(request, post, form)


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def edit_comment(request, post_id, comment_id):
    post = get_visible_post(request, post_id)
    comment = get_object_or_404(post.comments, pk=comment_id)
    if comment.author_id != request.user.pk:
        return redirect('blog:post_detail', post_id=post_id)
    form = CommentForm(
        request.POST if request.method == 'POST' else None, instance=comment
    )
    if form.is_valid():
        comment = form.save(commit=False)
        comment.save(update_fields=form.fields)
        return redirect('blog:post_detail', post_id=post_id)
    return render(
        request, 'blog/comment.html', {'comment': comment, 'form': form}
    )


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def delete_comment(request, post_id, comment_id):
    post = get_visible_post(request, post_id)
    comment = get_object_or_404(post.comments, pk=comment_id)
    if comment.author_id != request.user.pk:
        return redirect('blog:post_detail', post_id=post_id)
    if request.method == 'POST':
        comment.delete()
        return redirect('blog:post_detail', post_id=post_id)
    return render(request, 'blog/comment.html', {'comment': comment})
