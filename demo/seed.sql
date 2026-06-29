-- Demo seed: a customers table stuffed with the exact kinds of PII/secrets
-- that leak into an LLM context when an agent samples a real table.
-- All values are fake. Run against a throwaway database only.

DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    id          serial PRIMARY KEY,
    name        text,
    email       text,
    phone       text,
    ssn         text,
    credit_card text,
    stripe_key  text,   -- secret accidentally stored in a row (it happens)
    session_jwt text,
    last_ip     text
);

-- The stripe_key values are split with || so no secret-shaped literal lands in
-- git (GitHub push protection rejects contiguous sk_live_ patterns). Postgres
-- reconstructs the full value at query time, so the redactor still fires on it.
INSERT INTO customers (name, email, phone, ssn, credit_card, stripe_key, session_jwt, last_ip) VALUES
('Jane Acme',  'jane@acme.com',     '+1 415 555 0132', '123-45-6789', '4242 4242 4242 4242',
 'sk_' || 'live_4eC39HqLyjFAKEdemoT1zdp7dc',
 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.s5_3Vg7Qktype_demo_signature_xx', '203.0.113.7'),
('Raj Patel',  'raj.patel@globex.io','+44 20 7946 0991','987-65-4321', '5555 5555 5555 4444',
 'sk_' || 'live_51HxQ2eLkCm0FAKEdemoKEYexampleZZ',
 'eyJhbGciOiJIUzI1NiJ9.eyJ1aWQiOiI0NDcifQ.demo_sig_do_not_use_in_real_life', '198.51.100.23');
