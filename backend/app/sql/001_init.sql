-- Пользователи приложения
create table if not exists public.users (
    id uuid primary key,
    email text,
    username text,
    full_name text,
    avatar_url text,
    telegram_id text unique,
    rating integer not null default 0,
    settings_json jsonb
);

-- Индексы для часто используемых полей
create index if not exists idx_users_email on public.users (email);
create index if not exists idx_users_username on public.users (username);

-- RLS
alter table public.users enable row level security;

-- Политики: пользователь видит только себя, обновляет только себя
create policy if not exists users_select_self on public.users for select
    using (auth.uid() = id);

create policy if not exists users_update_self on public.users for update
    using (auth.uid() = id);

-- Разрешим вставку только сервисной ролью либо если id == auth.uid()
create policy if not exists users_insert_self on public.users for insert
    with check (auth.uid() = id);


-- Ордеры P2P
create table if not exists public.orders (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references public.users(id) on delete cascade,
    created_at timestamptz not null default now(),
    type text not null check (type in ('buy','sell')),
    asset text not null check (asset in ('USDT')),
    fiat text not null check (fiat in ('EUR','DINAR','RUB','USD')),
    price numeric not null,
    available_amount numeric not null,
    limit_min numeric not null,
    limit_max numeric not null,
    payment_methods text[] not null default '{}',
    terms text
);

create index if not exists idx_orders_type_price on public.orders (type, price);
create index if not exists idx_orders_owner on public.orders (owner_id);

alter table public.orders enable row level security;

-- Политики: SELECT публичный (все видят листинг)
create policy if not exists orders_select_public on public.orders for select
    using (true);

-- Политики: UPDATE/DELETE — только владелец
-- Для серверной роли будем выполнять проверки на бэке, поэтому оставим только SELECT публичный


